#!/usr/bin/env python3
"""
REBEL EM Discovery & Scale Analysis
Discovers all REBEL EM posts from WordPress sitemaps and analyzes scope.

Usage:
    python rebelem_discovery.py --sitemap     # Discover all URLs from sitemaps
    python rebelem_discovery.py --analyze     # Analyze discovered URLs
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
BASE_URL = "https://rebelem.com"
SITEMAP_INDEX_URL = "https://rebelem.com/sitemap_index.xml"
REQUEST_DELAY = 2.0  # Respectful delay between sitemap fetches

OUTPUT_DIR = Path(__file__).parent / "discovery"
OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class REBELEMDiscovery:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "EmergencyMedicineApp/1.0 (educational medical reference; contact: derickdavidjones@gmail.com)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

    def discover_from_sitemaps(self) -> list[dict]:
        """
        Discover all post URLs from the REBEL EM sitemap index.
        REBEL EM uses WordPress-generated sitemaps:
          - post-sitemap.xml (~1,000 posts)
          - post-sitemap2.xml (~247 posts)
          - rebel-review-sitemap.xml (structured reviews)
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

        # Filter to post-sitemap files only (skip page, category, author, tag, attachment sitemaps)
        post_sitemaps = [url for url in sitemap_locs if "post-sitemap" in url]
        rebel_review_sitemaps = [url for url in sitemap_locs if "rebel-review-sitemap" in url]
        other_sitemaps = [url for url in sitemap_locs if url not in post_sitemaps and url not in rebel_review_sitemaps]

        logger.info(f"Found {len(sitemap_locs)} sitemaps total:")
        logger.info(f"  Post sitemaps: {len(post_sitemaps)}")
        logger.info(f"  REBEL Review sitemaps: {len(rebel_review_sitemaps)}")
        logger.info(f"  Other sitemaps (skipped): {len(other_sitemaps)}")
        for url in other_sitemaps:
            logger.info(f"    - {url}")

        all_urls = []

        # Process post sitemaps (main blog posts)
        for sitemap_url in post_sitemaps:
            logger.info(f"  Fetching {sitemap_url}...")
            urls = self._parse_sitemap(sitemap_url)
            all_urls.extend(urls)
            logger.info(f"    → {len(urls)} URLs")
            time.sleep(REQUEST_DELAY)

        # Also include rebel-review sitemaps (structured clinical reviews)
        for sitemap_url in rebel_review_sitemaps:
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

                urls.append({
                    "url": url,
                    "slug": slug,
                    "lastmod": lastmod.text.strip() if lastmod else None,
                    "source": sitemap_url.split("/")[-1],
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
            "medical-category/",
            "page/",
        ]
        for pattern in skip_patterns:
            if pattern in slug:
                return True

        # Skip bare homepage
        if not slug:
            return True

        # Skip known non-clinical pages
        skip_slugs = [
            "donate",
            "swag",
            "disclaimer",
            "about",
            "contact",
            "advertising",
            "subscribe",
        ]
        if slug in skip_slugs:
            return True

        return False

    def analyze_urls(self, urls: list[dict]) -> dict:
        """Analyze discovered URLs for scope and categorization."""
        analysis = {
            "total_urls": len(urls),
            "by_source": Counter(),
            "by_year_modified": Counter(),
            "slug_patterns": Counter(),
            "sample_slugs": [],
        }

        for entry in urls:
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

            # Detect slug patterns
            slug = entry["slug"]
            if "rebel-core-cast" in slug:
                analysis["slug_patterns"]["core_cast"] += 1
            elif "rebel-cast" in slug:
                analysis["slug_patterns"]["rebel_cast"] += 1
            elif "rebel-review" in slug:
                analysis["slug_patterns"]["rebel_review"] += 1
            elif any(x in slug for x in ["trial", "rct", "study", "meta-analysis", "systematic-review"]):
                analysis["slug_patterns"]["trial_review"] += 1
            else:
                analysis["slug_patterns"]["clinical_post"] += 1

        # Convert Counters to dicts for JSON serialization
        analysis["by_source"] = dict(analysis["by_source"])
        analysis["by_year_modified"] = dict(sorted(analysis["by_year_modified"].items()))
        analysis["slug_patterns"] = dict(analysis["slug_patterns"])

        # Sample slugs from each pattern
        for pattern_name in analysis["slug_patterns"]:
            samples = []
            for entry in urls:
                slug = entry["slug"]
                match = False
                if pattern_name == "core_cast" and "rebel-core-cast" in slug:
                    match = True
                elif pattern_name == "rebel_cast" and "rebel-cast" in slug and "core-cast" not in slug:
                    match = True
                elif pattern_name == "rebel_review" and "rebel-review" in slug:
                    match = True
                elif pattern_name == "trial_review" and any(x in slug for x in ["trial", "rct", "study", "meta-analysis", "systematic-review"]):
                    match = True

                if match:
                    samples.append(slug)
                if len(samples) >= 5:
                    break

            analysis["sample_slugs"].append({
                "pattern": pattern_name,
                "count": analysis["slug_patterns"][pattern_name],
                "samples": samples,
            })

        return analysis

    def save_discovery(self, urls: list[dict], analysis: dict | None = None):
        """Save discovery results to JSON."""
        data = {
            "discovered_at": datetime.utcnow().isoformat() + "Z",
            "total_urls": len(urls),
            "urls": urls,
        }
        if analysis:
            data["analysis"] = analysis

        output_path = OUTPUT_DIR / "rebelem_discovery.json"
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved discovery data to {output_path}")

        # Also save a simple slug list for the bulk scraper
        slugs = sorted(set(entry["slug"] for entry in urls))
        slug_path = OUTPUT_DIR / "rebelem_slugs.json"
        with open(slug_path, "w") as f:
            json.dump({
                "discovered_at": data["discovered_at"],
                "count": len(slugs),
                "slugs": slugs,
            }, f, indent=2)
        logger.info(f"Saved {len(slugs)} unique slugs to {slug_path}")

        return output_path


def main():
    parser = argparse.ArgumentParser(description="REBEL EM Discovery & Analysis")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sitemap", action="store_true", help="Discover all URLs from sitemaps")
    group.add_argument("--analyze", action="store_true", help="Analyze previously discovered URLs")

    args = parser.parse_args()
    discovery = REBELEMDiscovery()

    if args.sitemap:
        urls = discovery.discover_from_sitemaps()
        if urls:
            analysis = discovery.analyze_urls(urls)
            discovery.save_discovery(urls, analysis)

            print(f"\n{'='*60}")
            print(f"REBEL EM DISCOVERY RESULTS")
            print(f"{'='*60}")
            print(f"  Total URLs:  {len(urls):,}")
            print(f"\n  By sitemap file:")
            for source, count in sorted(analysis["by_source"].items()):
                print(f"    {source}: {count:,}")
            print(f"\n  Content patterns:")
            for pattern, count in sorted(analysis["slug_patterns"].items(), key=lambda x: -x[1]):
                print(f"    {pattern}: {count:,}")
            print(f"\n  By year modified:")
            for year, count in sorted(analysis["by_year_modified"].items()):
                print(f"    {year}: {count:,}")
            print(f"{'='*60}")

    elif args.analyze:
        discovery_path = OUTPUT_DIR / "rebelem_discovery.json"
        if not discovery_path.exists():
            logger.error("No discovery data found. Run --sitemap first.")
            return

        with open(discovery_path) as f:
            data = json.load(f)

        urls = data["urls"]
        analysis = discovery.analyze_urls(urls)

        print(f"\n{'='*60}")
        print(f"REBEL EM ANALYSIS ({len(urls):,} URLs)")
        print(f"{'='*60}")
        print(f"\n  Content patterns:")
        for pattern, count in sorted(analysis["slug_patterns"].items(), key=lambda x: -x[1]):
            print(f"    {pattern}: {count:,}")
        print(f"\n  Samples per pattern:")
        for group in analysis.get("sample_slugs", []):
            print(f"\n    {group['pattern']} ({group['count']:,}):")
            for s in group["samples"]:
                print(f"      - {s}")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
