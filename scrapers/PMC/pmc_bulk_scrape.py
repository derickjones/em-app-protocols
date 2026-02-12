#!/usr/bin/env python3
"""
PMC Bulk Scraper — Parallel version
Scrapes PMC articles using concurrent workers with NCBI rate limiting.

Usage:
    # Run discovery first
    python3 pmc_discovery.py

    # Then bulk scrape with 10 workers
    python3 pmc_bulk_scrape.py --workers 10

    # Test with a small batch
    python3 pmc_bulk_scrape.py --workers 5 --limit 10

    # Resume a partial scrape (skips already-scraped articles)
    python3 pmc_bulk_scrape.py --workers 10 --resume

    # Force re-scrape everything
    python3 pmc_bulk_scrape.py --workers 10 --force

    # Retry only previously failed articles
    python3 pmc_bulk_scrape.py --workers 10 --retry-errors
"""

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

# Import the core scraper + discovery paths
from pmc_scraper import extract_article, PROCESSED_DIR, OUTPUT_DIR
from pmc_discovery import DISCOVERY_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pmc-bulk")

# Paths
SCRIPT_DIR = Path(__file__).parent
METADATA_DIR = SCRIPT_DIR / "metadata"
METADATA_DIR.mkdir(parents=True, exist_ok=True)

# Rate limiter: NCBI allows 10 req/sec with API key.
# Each article does 1-3 requests (BioC + possible HTML + images).
# With 10 workers, stagger starts by 0.15s each.
RATE_LIMIT_DELAY = 0.15  # seconds between thread dispatches


# ---------------------------------------------------------------------------
# Thread-safe progress tracker
# ---------------------------------------------------------------------------

class ProgressTracker:
    def __init__(self, total: int):
        self.total = total
        self.scraped = 0
        self.skipped = 0
        self.errors = 0
        self.full_text = 0
        self.abstract_only = 0
        self.error_articles = []
        self.lock = Lock()
        self.start_time = time.time()

    def record_success(self, pmcid: str, article_type: str):
        with self.lock:
            self.scraped += 1
            if article_type == "full_text":
                self.full_text += 1
            else:
                self.abstract_only += 1
            self._print_progress(pmcid, "✅")

    def record_skip(self, pmcid: str):
        with self.lock:
            self.skipped += 1
            self._print_progress(pmcid, "⏭")

    def record_error(self, pmcid: str, error: str):
        with self.lock:
            self.errors += 1
            self.error_articles.append({
                "pmcid": pmcid,
                "error": error,
                "time": datetime.now(timezone.utc).isoformat(),
            })
            self._print_progress(pmcid, "❌")

    def _print_progress(self, pmcid: str, status: str):
        done = self.scraped + self.skipped + self.errors
        elapsed = time.time() - self.start_time
        rate = done / elapsed if elapsed > 0 else 0
        remaining = (self.total - done) / rate if rate > 0 else 0

        pct = (done / self.total) * 100 if self.total > 0 else 0

        log.info(
            f"{status} [{done}/{self.total}] ({pct:.1f}%) "
            f"{pmcid:16s} | "
            f"Rate: {rate:.1f}/s | "
            f"ETA: {remaining/60:.0f}m | "
            f"✅{self.scraped} (📄{self.full_text} 📝{self.abstract_only}) "
            f"⏭{self.skipped} ❌{self.errors}"
        )

    def summary(self) -> dict:
        elapsed = time.time() - self.start_time
        return {
            "total": self.total,
            "scraped": self.scraped,
            "full_text": self.full_text,
            "abstract_only": self.abstract_only,
            "skipped": self.skipped,
            "errors": self.errors,
            "elapsed_seconds": round(elapsed, 1),
            "elapsed_minutes": round(elapsed / 60, 1),
            "articles_per_second": round((self.scraped + self.skipped) / elapsed, 2) if elapsed > 0 else 0,
        }


# ---------------------------------------------------------------------------
# Single article scrape (thread target)
# ---------------------------------------------------------------------------

def scrape_single(pmcid: str, journal: str, tracker: ProgressTracker, force: bool = False):
    """Scrape a single article — designed to run in a thread."""
    try:
        # Check if already scraped
        json_path = PROCESSED_DIR / f"{pmcid}.json"
        if not force and json_path.exists():
            tracker.record_skip(pmcid)
            return

        result = extract_article(pmcid, journal=journal)
        if result:
            tracker.record_success(pmcid, result.get("type", "abstract"))
        else:
            tracker.record_error(pmcid, "extract_article returned None (no full text or abstract)")

    except Exception as e:
        tracker.record_error(pmcid, str(e))


# ---------------------------------------------------------------------------
# Bulk scrape orchestrator
# ---------------------------------------------------------------------------

def bulk_scrape(articles: list[dict], workers: int = 10, force: bool = False):
    """
    Run parallel scrape across all articles with rate limiting.

    articles: list of {"pmcid": "PMC...", "journal": "..."}
    """
    # Ensure output dirs exist
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    tracker = ProgressTracker(len(articles))

    log.info(f"🚀 Starting PMC bulk scrape: {len(articles):,} articles, {workers} workers")
    log.info(f"   Force re-scrape: {force}")
    log.info(f"   Rate limit delay: {RATE_LIMIT_DELAY}s between dispatches")
    log.info(f"   Output: {OUTPUT_DIR}")
    log.info("")

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="worker") as executor:
        futures = {}

        # Stagger submissions to respect NCBI rate limits
        for article in articles:
            pmcid = article["pmcid"]
            journal = article.get("journal", "")
            future = executor.submit(scrape_single, pmcid, journal, tracker, force)
            futures[future] = pmcid
            time.sleep(RATE_LIMIT_DELAY)

        # Wait for all to complete
        for future in as_completed(futures):
            pmcid = futures[future]
            try:
                future.result()
            except Exception as e:
                tracker.record_error(pmcid, f"Unhandled: {str(e)}")

    # Print summary
    summary = tracker.summary()

    print("\n" + "=" * 70)
    print("📚 PMC BULK SCRAPE COMPLETE")
    print("=" * 70)
    print(f"  Total articles:      {summary['total']:,}")
    print(f"  Scraped:             {summary['scraped']:,}")
    print(f"    📄 Full-text:      {summary['full_text']:,}")
    print(f"    📝 Abstract-only:  {summary['abstract_only']:,}")
    print(f"  Skipped (cached):    {summary['skipped']:,}")
    print(f"  Errors:              {summary['errors']:,}")
    print(f"  Time:                {summary['elapsed_minutes']} minutes")
    print(f"  Rate:                {summary['articles_per_second']} articles/sec")
    print("=" * 70)

    # Save scrape log
    log_data = {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "errors": tracker.error_articles,
    }
    log_path = METADATA_DIR / "bulk_scrape_log.json"
    with open(log_path, "w") as f:
        json.dump(log_data, f, indent=2)
    print(f"\nLog saved to: {log_path}")

    # Save error list for retry
    if tracker.error_articles:
        err_path = METADATA_DIR / "bulk_scrape_errors.json"
        with open(err_path, "w") as f:
            json.dump(tracker.error_articles, f, indent=2)
        print(f"Error list saved to: {err_path} ({len(tracker.error_articles)} errors)")

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="PMC Bulk Parallel Scraper")
    parser.add_argument("--workers", type=int, default=10,
                        help="Number of parallel workers (default: 10)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip already-scraped articles (default behavior)")
    parser.add_argument("--force", action="store_true",
                        help="Re-scrape all articles even if cached")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of articles to scrape (0 = all)")
    parser.add_argument("--retry-errors", action="store_true",
                        help="Only retry previously failed articles")

    args = parser.parse_args()

    if args.retry_errors:
        # Retry only failed articles
        err_path = METADATA_DIR / "bulk_scrape_errors.json"
        if not err_path.exists():
            log.error("No error file found. Run a full scrape first.")
            return
        with open(err_path) as f:
            errors = json.load(f)
        # Convert error list to article format
        articles = [{"pmcid": e["pmcid"], "journal": ""} for e in errors]
        log.info(f"Retrying {len(articles)} failed articles...")
    else:
        # Load discovery data
        if not DISCOVERY_PATH.exists():
            log.error(f"Discovery data not found at {DISCOVERY_PATH}")
            log.error("Run: python3 pmc_discovery.py")
            return

        with open(DISCOVERY_PATH) as f:
            data = json.load(f)

        articles = data.get("articles", [])
        log.info(f"Loaded {len(articles):,} articles from discovery data")

    if args.limit > 0:
        articles = articles[:args.limit]
        log.info(f"Limited to first {args.limit} articles")

    if not articles:
        log.error("No articles to scrape!")
        return

    # Run the bulk scrape
    bulk_scrape(articles, workers=args.workers, force=args.force)


if __name__ == "__main__":
    main()
