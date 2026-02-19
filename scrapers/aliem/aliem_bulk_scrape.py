#!/usr/bin/env python3
"""
ALiEM Bulk Scraper — Scrapes all Track A pages (PV Cards + MEdIC Series).

Usage:
    # First run discovery:
    python aliem_discovery.py --sitemap

    # Then bulk scrape Track A pages:
    python aliem_bulk_scrape.py
    python aliem_bulk_scrape.py --workers 3 --resume
    python aliem_bulk_scrape.py --no-gcs --workers 2
"""

import argparse
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from aliem_scraper import extract_page

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DISCOVERY_DIR = Path(__file__).parent / "discovery"
TRACK_A_FILE = DISCOVERY_DIR / "aliem_track_a_slugs.json"
OUTPUT_DIR = Path(__file__).parent / "output"
PROCESSED_DIR = OUTPUT_DIR / "processed"
METADATA_DIR = OUTPUT_DIR / "metadata"
LOG_FILE = METADATA_DIR / "bulk_scrape_log.json"
ERROR_FILE = METADATA_DIR / "bulk_scrape_errors.json"
BULK_LOG_FILE = Path(__file__).parent / "bulk_scrape.log"

# 3 workers × 5s delay = ~1.67 req/s
DEFAULT_WORKERS = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(BULK_LOG_FILE), mode="a"),
    ],
)
log = logging.getLogger("aliem_bulk")


# ---------------------------------------------------------------------------
# Progress tracker (thread-safe)
# ---------------------------------------------------------------------------

class ProgressTracker:
    def __init__(self, total: int):
        self.total = total
        self.completed = 0
        self.succeeded = 0
        self.failed = 0
        self.skipped = 0
        self.errors: list[dict] = []
        self.results: list[dict] = []
        self.lock = Lock()
        self.start_time = time.time()

    def record_success(self, slug: str, title: str, sections: int, images: int):
        with self.lock:
            self.completed += 1
            self.succeeded += 1
            self.results.append({
                "slug": slug,
                "title": title,
                "status": "success",
                "sections": sections,
                "images": images,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            elapsed = time.time() - self.start_time
            rate = self.completed / elapsed * 60 if elapsed > 0 else 0
            log.info(
                f"  ✅ [{self.completed}/{self.total}] {title} "
                f"({sections}s, {images}i) — {rate:.1f}/min"
            )

    def record_failure(self, slug: str, error: str):
        with self.lock:
            self.completed += 1
            self.failed += 1
            self.errors.append({
                "slug": slug,
                "error": error,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            log.error(f"  ❌ [{self.completed}/{self.total}] {slug}: {error}")

    def record_skip(self, slug: str, reason: str):
        with self.lock:
            self.completed += 1
            self.skipped += 1
            self.results.append({
                "slug": slug,
                "status": "skipped",
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            log.info(f"  ⏭ [{self.completed}/{self.total}] {slug}: {reason}")

    def save(self):
        METADATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "w") as f:
            json.dump({
                "total": self.total,
                "completed": self.completed,
                "succeeded": self.succeeded,
                "failed": self.failed,
                "skipped": self.skipped,
                "elapsed_seconds": round(time.time() - self.start_time, 1),
                "results": self.results,
            }, f, indent=2)
        if self.errors:
            with open(ERROR_FILE, "w") as f:
                json.dump(self.errors, f, indent=2)


# ---------------------------------------------------------------------------
# Worker function
# ---------------------------------------------------------------------------

def scrape_slug(slug: str, tracker: ProgressTracker, upload_gcs: bool, resume: bool):
    """Scrape a single slug, called from thread pool."""
    safe = slug.replace("/", "_")

    # Resume: skip if already scraped
    if resume:
        json_path = PROCESSED_DIR / f"{safe}.json"
        if json_path.exists():
            tracker.record_skip(slug, "already scraped")
            return

    try:
        result = extract_page(slug, upload_gcs=upload_gcs)
        if result:
            tracker.record_success(
                slug,
                result["title"],
                len(result["sections"]),
                len(result["images"]),
            )
        else:
            tracker.record_failure(slug, "extract_page returned None")
    except Exception as e:
        tracker.record_failure(slug, str(e))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ALiEM Bulk Scraper (Track A)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Number of parallel workers")
    parser.add_argument("--resume", action="store_true", help="Skip already-scraped pages")
    parser.add_argument("--no-gcs", action="store_true", help="Skip GCS upload (local only)")
    parser.add_argument("--limit", type=int, help="Limit to N pages (for testing)")
    parser.add_argument("--slugs-file", type=str, help="Custom slugs file path")
    args = parser.parse_args()

    # Load slugs
    slugs_file = Path(args.slugs_file) if args.slugs_file else TRACK_A_FILE
    if not slugs_file.exists():
        log.error(
            f"Slugs file not found: {slugs_file}\n"
            f"Run discovery first: python aliem_discovery.py --sitemap"
        )
        return

    with open(slugs_file) as f:
        data = json.load(f)

    if isinstance(data, list):
        slugs = data
    elif isinstance(data, dict) and "slugs" in data:
        slugs = data["slugs"]
    else:
        log.error(f"Unexpected format in {slugs_file}")
        return

    if args.limit:
        slugs = slugs[:args.limit]

    upload_gcs = not args.no_gcs
    total = len(slugs)

    log.info(f"{'='*70}")
    log.info(f"ALiEM Bulk Scraper — Track A (PV Cards + MEdIC Series)")
    log.info(f"  Total pages:  {total}")
    log.info(f"  Workers:      {args.workers}")
    log.info(f"  GCS upload:   {upload_gcs}")
    log.info(f"  Resume:       {args.resume}")
    log.info(f"  Bucket:       {os.environ.get('ALIEM_BUCKET', 'clinical-assistant-457902-aliem')}")
    log.info(f"{'='*70}")

    tracker = ProgressTracker(total)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(scrape_slug, slug, tracker, upload_gcs, args.resume): slug
            for slug in slugs
        }
        try:
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    slug = futures[future]
                    tracker.record_failure(slug, f"Unhandled: {str(e)}")
                # Save progress every 20 pages
                if tracker.completed % 20 == 0:
                    tracker.save()
        except KeyboardInterrupt:
            log.warning("\n⚠️ Interrupted! Saving progress...")
            tracker.save()
            pool.shutdown(wait=False, cancel_futures=True)
            return

    tracker.save()

    elapsed = time.time() - tracker.start_time
    rate = tracker.completed / elapsed * 60 if elapsed > 0 else 0
    log.info(f"\n{'='*70}")
    log.info(f"DONE — ALiEM Track A Bulk Scrape")
    log.info(f"  Succeeded: {tracker.succeeded}/{total}")
    log.info(f"  Failed:    {tracker.failed}/{total}")
    log.info(f"  Skipped:   {tracker.skipped}/{total}")
    log.info(f"  Elapsed:   {elapsed/60:.1f} min ({rate:.1f} pages/min)")
    log.info(f"  Output:    {PROCESSED_DIR}")
    log.info(f"{'='*70}")

    if tracker.errors:
        log.warning(f"\nErrors saved to: {ERROR_FILE}")
        for err in tracker.errors[:10]:
            log.warning(f"  {err['slug']}: {err['error']}")
        if len(tracker.errors) > 10:
            log.warning(f"  ... and {len(tracker.errors) - 10} more")


if __name__ == "__main__":
    main()
