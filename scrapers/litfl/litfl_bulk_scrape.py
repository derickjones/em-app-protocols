#!/usr/bin/env python3
"""
LITFL Bulk Scraper
Parallel scraper with progress tracking, resume support, and error retry.

Usage:
    python litfl_bulk_scrape.py                     # Scrape all discovered pages
    python litfl_bulk_scrape.py --limit 50          # Scrape first 50 pages
    python litfl_bulk_scrape.py --workers 5         # Use 5 parallel workers
    python litfl_bulk_scrape.py --resume            # Resume from last run
    python litfl_bulk_scrape.py --retry-errors      # Retry previously failed pages
    python litfl_bulk_scrape.py --force              # Re-scrape already completed pages
    python litfl_bulk_scrape.py --no-gcs            # Skip GCS uploads (local only)
"""

import argparse
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from litfl_scraper import extract_page

# Configuration
DISCOVERY_PATH = Path(__file__).parent / "discovery" / "litfl_discovery.json"
PROGRESS_DIR = Path(__file__).parent / "output" / "metadata"
PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
PROGRESS_FILE = PROGRESS_DIR / "bulk_scrape_log.json"
ERROR_FILE = PROGRESS_DIR / "bulk_scrape_errors.json"

DEFAULT_WORKERS = 3
REQUEST_DELAY = 1.5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ProgressTracker:
    """Thread-safe progress tracker with disk persistence."""

    def __init__(self):
        self.completed: set[str] = set()
        self.errors: dict[str, dict] = {}
        self.stats = {
            "started_at": None,
            "total": 0,
            "completed": 0,
            "errors": 0,
            "skipped": 0,
            "images_downloaded": 0,
        }

    def load(self) -> None:
        """Load previous progress from disk."""
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE) as f:
                data = json.load(f)
            self.completed = set(data.get("completed_slugs", []))
            self.stats = data.get("stats", self.stats)
            logger.info(f"Loaded progress: {len(self.completed)} completed")

        if ERROR_FILE.exists():
            with open(ERROR_FILE) as f:
                self.errors = json.load(f)
            logger.info(f"Loaded errors: {len(self.errors)} previous errors")

    def save(self) -> None:
        """Save current progress to disk."""
        data = {
            "last_saved": datetime.utcnow().isoformat() + "Z",
            "stats": self.stats,
            "completed_slugs": sorted(self.completed),
        }
        with open(PROGRESS_FILE, "w") as f:
            json.dump(data, f, indent=2)

        if self.errors:
            with open(ERROR_FILE, "w") as f:
                json.dump(self.errors, f, indent=2)

    def mark_completed(self, slug: str, image_count: int = 0) -> None:
        self.completed.add(slug)
        self.stats["completed"] += 1
        self.stats["images_downloaded"] += image_count

    def mark_error(self, slug: str, error: str) -> None:
        self.errors[slug] = {
            "error": str(error),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self.stats["errors"] += 1

    def mark_skipped(self) -> None:
        self.stats["skipped"] += 1

    def is_completed(self, slug: str) -> bool:
        return slug in self.completed


def scrape_slug(slug: str, upload_gcs: bool = True) -> dict:
    """Scrape a single slug. Returns result dict."""
    try:
        result = extract_page(slug, upload_gcs=upload_gcs)
        if result:
            return {
                "slug": slug,
                "status": "success",
                "title": result.get("title", ""),
                "images": len(result.get("images", [])),
                "sections": len(result.get("sections", [])),
            }
        else:
            return {
                "slug": slug,
                "status": "error",
                "error": "extract_page returned None",
            }
    except Exception as e:
        return {
            "slug": slug,
            "status": "error",
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(description="LITFL Bulk Scraper")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                        help=f"Number of parallel workers (default: {DEFAULT_WORKERS})")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of pages to scrape")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from previous run, skipping completed pages")
    parser.add_argument("--force", action="store_true",
                        help="Re-scrape even if already completed")
    parser.add_argument("--retry-errors", action="store_true",
                        help="Retry previously failed pages only")
    parser.add_argument("--no-gcs", action="store_true",
                        help="Skip GCS uploads (local only)")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY,
                        help=f"Delay between requests in seconds (default: {REQUEST_DELAY})")

    args = parser.parse_args()

    # Load discovery data
    if not DISCOVERY_PATH.exists():
        logger.error("No discovery data found. Run litfl_discovery.py --sitemap first.")
        return

    with open(DISCOVERY_PATH) as f:
        discovery = json.load(f)

    all_urls = discovery["urls"]
    logger.info(f"Loaded {len(all_urls)} discovered URLs")

    # Progress tracking
    tracker = ProgressTracker()
    if args.resume or args.retry_errors:
        tracker.load()

    # Determine which slugs to scrape
    if args.retry_errors:
        slugs_to_scrape = list(tracker.errors.keys())
        logger.info(f"Retrying {len(slugs_to_scrape)} previously failed pages")
        # Clear old errors for retried slugs
        for slug in slugs_to_scrape:
            if slug in tracker.errors:
                del tracker.errors[slug]
    else:
        slugs_to_scrape = [entry["slug"] for entry in all_urls]

    # Filter out completed if resuming (not forced)
    if args.resume and not args.force:
        before = len(slugs_to_scrape)
        slugs_to_scrape = [s for s in slugs_to_scrape if not tracker.is_completed(s)]
        skipped = before - len(slugs_to_scrape)
        if skipped:
            logger.info(f"Skipping {skipped} already completed pages")
            tracker.stats["skipped"] = skipped

    # Apply limit
    if args.limit:
        slugs_to_scrape = slugs_to_scrape[:args.limit]

    total = len(slugs_to_scrape)
    if total == 0:
        logger.info("No pages to scrape. Done!")
        return

    logger.info(f"Scraping {total} pages with {args.workers} workers...")
    tracker.stats["total"] = total
    tracker.stats["started_at"] = datetime.utcnow().isoformat() + "Z"

    upload_gcs = not args.no_gcs

    completed = 0
    errors = 0
    save_interval = 25  # Save progress every N pages

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit jobs in batches to control rate
        futures = {}
        for slug in slugs_to_scrape:
            future = executor.submit(scrape_slug, slug, upload_gcs)
            futures[future] = slug

        for future in as_completed(futures):
            slug = futures[future]
            try:
                result = future.result()

                if result["status"] == "success":
                    completed += 1
                    tracker.mark_completed(slug, result.get("images", 0))
                    logger.info(
                        f"[{completed + errors}/{total}] ✓ {slug} "
                        f"({result.get('sections', 0)} sections, "
                        f"{result.get('images', 0)} images)"
                    )
                else:
                    errors += 1
                    tracker.mark_error(slug, result.get("error", "Unknown"))
                    logger.warning(f"[{completed + errors}/{total}] ✗ {slug}: {result.get('error', 'Unknown')}")

            except Exception as e:
                errors += 1
                tracker.mark_error(slug, str(e))
                logger.error(f"[{completed + errors}/{total}] ✗ {slug}: {e}")

            # Periodic save
            if (completed + errors) % save_interval == 0:
                tracker.save()

            # Rate limiting
            time.sleep(args.delay)

    # Final save
    tracker.save()

    # Summary
    elapsed = ""
    if tracker.stats.get("started_at"):
        start_str = tracker.stats["started_at"]
        # Handle both naive and aware datetime strings
        if start_str.endswith("Z"):
            start_str = start_str[:-1] + "+00:00"
        start = datetime.fromisoformat(start_str)
        now = datetime.now(start.tzinfo)
        delta = now - start
        elapsed = f" in {delta.total_seconds():.0f}s"

    print(f"\n{'='*60}")
    print(f"LITFL BULK SCRAPE COMPLETE{elapsed}")
    print(f"{'='*60}")
    print(f"  Total:       {total}")
    print(f"  Completed:   {completed}")
    print(f"  Errors:      {errors}")
    print(f"  Images:      {tracker.stats['images_downloaded']}")
    if tracker.stats.get("skipped"):
        print(f"  Skipped:     {tracker.stats['skipped']}")
    if errors:
        print(f"\n  Error log: {ERROR_FILE}")
        print(f"  Run with --retry-errors to retry failed pages")
    print(f"  Progress:    {PROGRESS_FILE}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
