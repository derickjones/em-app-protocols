#!/usr/bin/env python3
"""
WikEM Bulk Scraper — Parallel version
Scrapes all WikEM topics using concurrent workers.

Usage:
    # First discover all topics (if not done yet)
    python3 wikem_scraper.py --discover

    # Then run bulk scrape with 20 workers
    python3 wikem_bulk_scrape.py --workers 20

    # Resume a partial scrape (skips already-scraped pages)
    python3 wikem_bulk_scrape.py --workers 20 --resume

    # Force re-scrape everything
    python3 wikem_bulk_scrape.py --workers 20 --force
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

# Import the existing scraper functions
from wikem_scraper import (
    extract_page,
    discover_topic_urls,
    PROCESSED_DIR,
    METADATA_DIR,
    OUTPUT_DIR,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("wikem_bulk")

# Thread-safe counters
class ProgressTracker:
    def __init__(self, total: int):
        self.total = total
        self.scraped = 0
        self.skipped = 0
        self.errors = 0
        self.error_slugs = []
        self.lock = Lock()
        self.start_time = time.time()
    
    def record_success(self, slug: str):
        with self.lock:
            self.scraped += 1
            self._print_progress(slug, "✅")
    
    def record_skip(self, slug: str):
        with self.lock:
            self.skipped += 1
            self._print_progress(slug, "⏭")
    
    def record_error(self, slug: str, error: str):
        with self.lock:
            self.errors += 1
            self.error_slugs.append({"slug": slug, "error": error, "time": datetime.now(timezone.utc).isoformat()})
            self._print_progress(slug, "❌")
    
    def _print_progress(self, slug: str, status: str):
        done = self.scraped + self.skipped + self.errors
        elapsed = time.time() - self.start_time
        rate = done / elapsed if elapsed > 0 else 0
        remaining = (self.total - done) / rate if rate > 0 else 0
        
        pct = (done / self.total) * 100 if self.total > 0 else 0
        
        log.info(
            f"{status} [{done}/{self.total}] ({pct:.1f}%) "
            f"{slug[:40]:40s} | "
            f"Rate: {rate:.1f}/s | "
            f"ETA: {remaining/60:.0f}m | "
            f"✅{self.scraped} ⏭{self.skipped} ❌{self.errors}"
        )
    
    def summary(self) -> dict:
        elapsed = time.time() - self.start_time
        return {
            "total": self.total,
            "scraped": self.scraped,
            "skipped": self.skipped,
            "errors": self.errors,
            "elapsed_seconds": round(elapsed, 1),
            "elapsed_minutes": round(elapsed / 60, 1),
            "pages_per_second": round((self.scraped + self.skipped) / elapsed, 2) if elapsed > 0 else 0,
        }


def scrape_single(slug: str, tracker: ProgressTracker, force: bool = False):
    """Scrape a single topic — designed to run in a thread."""
    try:
        # Check if already scraped
        json_path = PROCESSED_DIR / f"{slug.replace('/', '_')}.json"
        if not force and json_path.exists():
            tracker.record_skip(slug)
            return
        
        result = extract_page(slug)
        if result:
            tracker.record_success(slug)
        else:
            tracker.record_error(slug, "extract_page returned None")
    except Exception as e:
        tracker.record_error(slug, str(e))


def bulk_scrape(slugs: list[str], workers: int = 20, force: bool = False):
    """Run parallel scrape across all slugs."""
    
    # Ensure output dirs exist
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    
    tracker = ProgressTracker(len(slugs))
    
    log.info(f"🚀 Starting bulk scrape: {len(slugs)} topics, {workers} workers")
    log.info(f"   Force re-scrape: {force}")
    log.info(f"   Output: {OUTPUT_DIR}")
    log.info("")
    
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="worker") as executor:
        futures = {
            executor.submit(scrape_single, slug, tracker, force): slug
            for slug in slugs
        }
        
        # Wait for all to complete
        for future in as_completed(futures):
            slug = futures[future]
            try:
                future.result()  # Raise any unhandled exceptions
            except Exception as e:
                tracker.record_error(slug, f"Unhandled: {str(e)}")
    
    # Print summary
    summary = tracker.summary()
    
    print("\n" + "=" * 70)
    print("🏥 WIKEM BULK SCRAPE COMPLETE")
    print("=" * 70)
    print(f"  Total topics:     {summary['total']:,}")
    print(f"  Scraped:          {summary['scraped']:,}")
    print(f"  Skipped (cached): {summary['skipped']:,}")
    print(f"  Errors:           {summary['errors']:,}")
    print(f"  Time:             {summary['elapsed_minutes']} minutes")
    print(f"  Rate:             {summary['pages_per_second']} pages/sec")
    print("=" * 70)
    
    # Save scrape log
    log_data = {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "errors": tracker.error_slugs,
    }
    log_path = METADATA_DIR / "bulk_scrape_log.json"
    with open(log_path, "w") as f:
        json.dump(log_data, f, indent=2)
    print(f"\nLog saved to: {log_path}")
    
    # Save error list for retry
    if tracker.error_slugs:
        err_path = METADATA_DIR / "bulk_scrape_errors.json"
        with open(err_path, "w") as f:
            json.dump(tracker.error_slugs, f, indent=2)
        print(f"Error list saved to: {err_path}")
    
    return summary


def main():
    parser = argparse.ArgumentParser(description="WikEM Bulk Parallel Scraper")
    parser.add_argument("--workers", type=int, default=20, help="Number of parallel workers (default: 20)")
    parser.add_argument("--resume", action="store_true", help="Skip already-scraped pages (default behavior)")
    parser.add_argument("--force", action="store_true", help="Re-scrape all pages even if cached")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of pages to scrape (0 = all)")
    parser.add_argument("--retry-errors", action="store_true", help="Only retry previously failed pages")
    
    args = parser.parse_args()
    
    # Load topic URLs from discovery data
    discovery_path = Path(__file__).parent / "discovery" / "wikem_discovery.json"
    urls_path = METADATA_DIR / "topic_urls.json"
    
    if args.retry_errors:
        # Retry only failed pages
        err_path = METADATA_DIR / "bulk_scrape_errors.json"
        if not err_path.exists():
            log.error("No error file found. Run a full scrape first.")
            return
        with open(err_path) as f:
            errors = json.load(f)
        slugs = [e["slug"] for e in errors]
        log.info(f"Retrying {len(slugs)} failed pages...")
    elif discovery_path.exists():
        # Use pre-built discovery data (fast — no network calls)
        log.info(f"Loading topics from discovery data: {discovery_path}")
        with open(discovery_path) as f:
            data = json.load(f)
        
        # Get clinical topics + procedures + medications (skip admin/other)
        scrape_categories = ['clinical_topics', 'procedures', 'medications']
        slugs = []
        for cat in scrape_categories:
            for item in data.get('classifications', {}).get(cat, []):
                title = item.get('title', '')
                if title and title != 'Main_Page':
                    slugs.append(title)
        
        log.info(f"Found {len(slugs)} topics to scrape from discovery data")
    elif urls_path.exists():
        # Fallback to topic_urls.json from old discover
        with open(urls_path) as f:
            data = json.load(f)
        slugs = data["slugs"]
    else:
        log.error("No discovery data found. Run: python3 wikem_discovery.py --sitemap")
        return
    
    if args.limit > 0:
        slugs = slugs[:args.limit]
        log.info(f"Limited to first {args.limit} topics")
    
    # Run the bulk scrape
    bulk_scrape(slugs, workers=args.workers, force=args.force)


if __name__ == "__main__":
    main()
