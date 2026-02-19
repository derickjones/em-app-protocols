#!/usr/bin/env python3
"""
ALiEM Discovery — Track A (PV Cards + MEdIC Series)
Discovers CC BY-NC-ND 3.0 licensed posts from aliem.com sitemaps.

Track A only scrapes content explicitly licensed under Creative Commons:
  - Paucis Verbis (PV) Cards — clinical reference cards
  - MEdIC Series — medical ethics cases

Usage:
    python aliem_discovery.py --sitemap          # Discover all post URLs, tag by track
    python aliem_discovery.py --sitemap --track-a # Show only Track A (CC licensed)
    python aliem_discovery.py --analyze           # Analyze discovered URLs
"""

import argparse
import json
import logging
import re
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# Configuration
BASE_URL = "https://www.aliem.com"
SITEMAP_INDEX_URL = "https://www.aliem.com/sitemap_index.xml"
REQUEST_DELAY = 2.0  # Delay between sitemap fetches

OUTPUT_DIR = Path(__file__).parent / "discovery"
OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Track A slug patterns — CC BY-NC-ND 3.0 licensed content
# ---------------------------------------------------------------------------
# ALiEM footer: "copyrighted as 'All Rights Reserved' except for our
# Paucis Verbis cards and MEdIC Series"

PV_CARD_PATTERNS = [
    "paucis-verbis-",
    "pv-card-",
    "pv-",
    "tox-meds-pv-cards",
]

MEDIC_PATTERNS = [
    "medic-series-",
    "medic-case-",
    "medic-",
]


def is_track_a(slug: str) -> bool:
    """Check if a slug belongs to Track A (CC licensed PV Cards or MEdIC)."""
    slug_lower = slug.lower()
    for pattern in PV_CARD_PATTERNS:
        if pattern in slug_lower:
            return True
    for pattern in MEDIC_PATTERNS:
        if pattern in slug_lower:
            return True
    return False


def get_track_a_type(slug: str) -> str | None:
    """Return the Track A content type, or None if not Track A."""
    slug_lower = slug.lower()
    for pattern in PV_CARD_PATTERNS:
        if pattern in slug_lower:
            return "pv_card"
    for pattern in MEDIC_PATTERNS:
        if pattern in slug_lower:
            return "medic"
    return None


class ALiEMDiscovery:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "EmergencyMedicineApp/1.0 (educational medical reference; contact: derickdavidjones@gmail.com)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

    def discover_from_sitemaps(self) -> list[dict]:
        """
        Discover all post URLs from the ALiEM sitemap index.
        ALiEM uses Yoast SEO sitemaps:
          - post-sitemap.xml  (~1,000 posts)
          - post-sitemap2.xml (~1,000 posts)
          - post-sitemap3.xml (~500+ posts)
        """
        logger.info("Fetching sitemap index...")

        try:
            resp = self.session.get(SITEMAP_INDEX_URL, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch sitemap index: {e}")
            return []

        soup = BeautifulSoup(resp.content, "lxml-xml")
        sitemap_locs = [loc.text.strip() for loc in soup.find_all("loc")]

        # Filter to post-sitemap files only
        post_sitemaps = [url for url in sitemap_locs if "post-sitemap" in url]
        other_sitemaps = [url for url in sitemap_locs if url not in post_sitemaps]

        logger.info(f"Found {len(sitemap_locs)} sitemaps total:")
        logger.info(f"  Post sitemaps: {len(post_sitemaps)}")
        logger.info(f"  Other sitemaps (skipped): {len(other_sitemaps)}")
        for url in other_sitemaps:
            logger.info(f"    - {url}")

        all_urls = []

        for sitemap_url in post_sitemaps:
            logger.info(f"  Fetching {sitemap_url}...")
            urls = self._parse_sitemap(sitemap_url)
            all_urls.extend(urls)
            logger.info(f"    → {len(urls)} URLs")
            time.sleep(REQUEST_DELAY)

        logger.info(f"\nTotal discovered: {len(all_urls)} URLs")
        return all_urls

    def _parse_sitemap(self, sitemap_url: str) -> list[dict]:
        """Parse a single sitemap XML file and extract URLs with metadata."""
        try:
            resp = self.session.get(sitemap_url, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch {sitemap_url}: {e}")
            return []

        soup = BeautifulSoup(resp.content, "lxml-xml")
        urls = []

        for url_elem in soup.find_all("url"):
            loc = url_elem.find("loc")
            lastmod = url_elem.find("lastmod")

            if loc:
                url = loc.text.strip()
                slug = self._url_to_slug(url)

                if not slug:
                    continue

                # Skip non-content pages
                if self._should_skip(slug):
                    continue

                # Determine track
                track_type = get_track_a_type(slug)
                track = "A" if track_type else "B"

                urls.append({
                    "url": url,
                    "slug": slug,
                    "lastmod": lastmod.text.strip() if lastmod else None,
                    "source": sitemap_url.split("/")[-1],
                    "track": track,
                    "track_a_type": track_type,
                })

        return urls

    def _url_to_slug(self, url: str) -> str:
        """Convert a full URL to a slug."""
        path = urlparse(url).path.strip("/")
        return path if path else ""

    def _should_skip(self, slug: str) -> bool:
        """Check if a URL should be skipped (non-content pages)."""
        skip_patterns = [
            "wp-content",
            "wp-admin",
            "wp-login",
            "feed",
            "comments",
            "author/",
            "category/",
            "tag/",
            "page/",
            "attachment",
        ]
        for pattern in skip_patterns:
            if pattern in slug:
                return True

        # Skip bare homepage
        if not slug:
            return True

        # Skip known non-clinical pages
        skip_slugs = [
            "disclaimer",
            "disclaimer-privacy-copyright",
            "terms-of-use",
            "about",
            "about-us",
            "contact",
            "subscribe",
            "meet-the-team",
            "culture-book",
        ]
        if slug in skip_slugs:
            return True

        return False

    def analyze_urls(self, urls: list[dict]) -> dict:
        """Analyze discovered URLs for scope and categorization."""
        analysis = {
            "total_urls": len(urls),
            "by_track": Counter(),
            "by_track_a_type": Counter(),
            "by_source": Counter(),
            "by_year_modified": Counter(),
            "content_patterns": Counter(),
            "track_a_samples": [],
            "track_b_samples": [],
        }

        for entry in urls:
            # Count by track
            analysis["by_track"][entry.get("track", "B")] += 1

            # Count Track A subtypes
            ta_type = entry.get("track_a_type")
            if ta_type:
                analysis["by_track_a_type"][ta_type] += 1

            # Count by source sitemap
            analysis["by_source"][entry.get("source", "unknown")] += 1

            # Count by year of last modification
            lastmod = entry.get("lastmod")
            if lastmod:
                try:
                    year = lastmod[:4]
                    analysis["by_year_modified"][year] += 1
                except (IndexError, TypeError):
                    pass

            # Detect content patterns from slugs
            slug = entry["slug"]
            if "paucis-verbis" in slug or "pv-card" in slug or slug.startswith("pv-"):
                analysis["content_patterns"]["pv_card"] += 1
            elif "medic-" in slug:
                analysis["content_patterns"]["medic"] += 1
            elif "saem-clinical-image" in slug:
                analysis["content_patterns"]["saem_clinical_image"] += 1
            elif "trick-of-trade" in slug or "trick-of-the-trade" in slug or slug.startswith("trick-"):
                analysis["content_patterns"]["trick_of_trade"] += 1
            elif "splinter-series" in slug:
                analysis["content_patterns"]["splinter_series"] += 1
            elif "pem-" in slug:
                analysis["content_patterns"]["pem_pearls"] += 1
            elif "acmt-" in slug:
                analysis["content_patterns"]["acmt_tox"] += 1
            elif "air-" in slug or "aliem-air" in slug:
                analysis["content_patterns"]["air_module"] += 1
            elif "emrad-" in slug:
                analysis["content_patterns"]["emrad"] += 1
            elif "idea-series" in slug or "idea-" in slug:
                analysis["content_patterns"]["idea_series"] += 1
            elif "aliemu-" in slug:
                analysis["content_patterns"]["aliemu"] += 1
            elif "em-match-advice" in slug:
                analysis["content_patterns"]["match_advice"] += 1
            elif "how-i-work-smarter" in slug or "how-i-educate" in slug:
                analysis["content_patterns"]["lifestyle"] += 1
            elif "healthy-in-em" in slug:
                analysis["content_patterns"]["wellness"] += 1
            else:
                analysis["content_patterns"]["other_clinical"] += 1

            # Collect samples
            if entry.get("track") == "A" and len(analysis["track_a_samples"]) < 20:
                analysis["track_a_samples"].append(slug)
            elif entry.get("track") == "B" and len(analysis["track_b_samples"]) < 10:
                analysis["track_b_samples"].append(slug)

        # Convert Counters to dicts for JSON serialization
        analysis["by_track"] = dict(analysis["by_track"])
        analysis["by_track_a_type"] = dict(analysis["by_track_a_type"])
        analysis["by_source"] = dict(analysis["by_source"])
        analysis["by_year_modified"] = dict(sorted(analysis["by_year_modified"].items()))
        analysis["content_patterns"] = dict(sorted(analysis["content_patterns"].items(), key=lambda x: -x[1]))

        return analysis

    def save_discovery(self, urls: list[dict], analysis: dict | None = None):
        """Save discovery results to JSON."""
        data = {
            "discovered_at": datetime.utcnow().isoformat() + "Z",
            "total_urls": len(urls),
            "track_a_count": sum(1 for u in urls if u.get("track") == "A"),
            "track_b_count": sum(1 for u in urls if u.get("track") == "B"),
            "urls": urls,
        }
        if analysis:
            data["analysis"] = analysis

        output_path = OUTPUT_DIR / "aliem_discovery.json"
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved discovery data to {output_path}")

        # Also save Track A slug list for the bulk scraper
        track_a_slugs = sorted(set(
            entry["slug"] for entry in urls if entry.get("track") == "A"
        ))
        slug_path = OUTPUT_DIR / "aliem_track_a_slugs.json"
        with open(slug_path, "w") as f:
            json.dump({
                "discovered_at": data["discovered_at"],
                "count": len(track_a_slugs),
                "description": "CC BY-NC-ND 3.0 licensed content: PV Cards + MEdIC Series",
                "slugs": track_a_slugs,
            }, f, indent=2)
        logger.info(f"Saved {len(track_a_slugs)} Track A slugs to {slug_path}")

        return output_path


def main():
    parser = argparse.ArgumentParser(description="ALiEM Discovery & Analysis")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sitemap", action="store_true", help="Discover all URLs from sitemaps")
    group.add_argument("--analyze", action="store_true", help="Analyze previously discovered URLs")
    parser.add_argument("--track-a", action="store_true", help="Only show Track A results")

    args = parser.parse_args()
    discovery = ALiEMDiscovery()

    if args.sitemap:
        urls = discovery.discover_from_sitemaps()
        if urls:
            analysis = discovery.analyze_urls(urls)
            discovery.save_discovery(urls, analysis)

            track_a = [u for u in urls if u.get("track") == "A"]
            track_b = [u for u in urls if u.get("track") == "B"]

            print(f"\n{'='*60}")
            print(f"ALiEM DISCOVERY RESULTS")
            print(f"{'='*60}")
            print(f"  Total URLs:     {len(urls):,}")
            print(f"  Track A (CC):   {len(track_a):,}  ← Safe to scrape")
            print(f"  Track B (ARR):  {len(track_b):,}  ← Needs permission")
            print(f"\n  By sitemap file:")
            for source, count in sorted(analysis["by_source"].items()):
                print(f"    {source}: {count:,}")
            print(f"\n  Track A breakdown:")
            for subtype, count in sorted(analysis["by_track_a_type"].items(), key=lambda x: -x[1]):
                print(f"    {subtype}: {count:,}")
            print(f"\n  Content patterns (all tracks):")
            for pattern, count in sorted(analysis["content_patterns"].items(), key=lambda x: -x[1]):
                marker = " ✅" if pattern in ("pv_card", "medic") else ""
                print(f"    {pattern}: {count:,}{marker}")

            if args.track_a:
                print(f"\n  Track A URLs ({len(track_a)}):")
                for entry in track_a:
                    print(f"    [{entry['track_a_type']}] {entry['slug']}")

            print(f"\n  Track A samples:")
            for slug in analysis.get("track_a_samples", [])[:15]:
                print(f"    - {slug}")
            print(f"{'='*60}")

    elif args.analyze:
        discovery_path = OUTPUT_DIR / "aliem_discovery.json"
        if not discovery_path.exists():
            logger.error("No discovery data found. Run --sitemap first.")
            return

        with open(discovery_path) as f:
            data = json.load(f)

        urls = data["urls"]
        analysis = discovery.analyze_urls(urls)

        track_a = [u for u in urls if u.get("track") == "A"]

        print(f"\n{'='*60}")
        print(f"ALiEM ANALYSIS ({len(urls):,} total, {len(track_a):,} Track A)")
        print(f"{'='*60}")
        print(f"\n  Track A breakdown:")
        for subtype, count in sorted(analysis["by_track_a_type"].items(), key=lambda x: -x[1]):
            print(f"    {subtype}: {count:,}")
        print(f"\n  Content patterns (all):")
        for pattern, count in sorted(analysis["content_patterns"].items(), key=lambda x: -x[1]):
            print(f"    {pattern}: {count:,}")

        if args.track_a:
            print(f"\n  All Track A URLs:")
            for entry in track_a:
                print(f"    [{entry['track_a_type']}] {entry['slug']}")

        print(f"{'='*60}")


if __name__ == "__main__":
    main()
