#!/usr/bin/env python3
"""
WikEM Scraper — Phase 1
Scrapes wikem.org topic pages and extracts structured content.

Usage:
    # Test with a single page
    python wikem_scraper.py --test

    # Scrape a specific topic
    python wikem_scraper.py --topic Hyponatremia

    # Discover all topic URLs from the sitemap
    python wikem_scraper.py --discover

    # Scrape all discovered topics
    python wikem_scraper.py --all
"""

import argparse
import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, unquote

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "https://wikem.org"
WIKI_PREFIX = "/wiki/"
SITEMAP_URL = "https://www.wikem.org/w/sitemap.xml"

OUTPUT_DIR = Path(__file__).parent / "output"
RAW_DIR = OUTPUT_DIR / "raw"
PROCESSED_DIR = OUTPUT_DIR / "processed"
METADATA_DIR = OUTPUT_DIR / "metadata"

REQUEST_DELAY = 1.5  # seconds between requests (be polite)
USER_AGENT = (
    "EmergencyMedicineApp/1.0 "
    "(educational medical reference; contact: derickdavidjones@gmail.com)"
)

# Namespace prefixes to skip (non-article pages)
SKIP_PREFIXES = [
    "User:", "Talk:", "Template:", "Category:", "File:", "Help:",
    "WikEM:", "Special:", "MediaWiki:", "Portal:", "Module:",
    "User_talk:", "Template_talk:", "Category_talk:", "WikEM_talk:",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("wikem")

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def fetch(url: str) -> requests.Response | None:
    """GET a URL with rate limiting and error handling."""
    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        time.sleep(REQUEST_DELAY)
        return resp
    except requests.RequestException as e:
        log.error(f"Failed to fetch {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Sitemap / Discovery
# ---------------------------------------------------------------------------

def discover_topic_urls() -> list[str]:
    """
    Parse the WikEM sitemap to discover all article URLs.
    Returns a list of topic slugs (e.g. "Hyponatremia").
    """
    log.info("Fetching sitemap index...")
    resp = fetch(SITEMAP_URL)
    if not resp:
        log.error("Could not fetch sitemap index")
        return []

    soup = BeautifulSoup(resp.text, "lxml-xml")

    # The sitemap index points to individual sitemap files
    sitemap_locs = [loc.text for loc in soup.find_all("loc")]
    log.info(f"Found {len(sitemap_locs)} sitemap file(s)")

    all_urls: list[str] = []
    for sitemap_url in sitemap_locs:
        log.info(f"  Fetching {sitemap_url}...")
        resp = fetch(sitemap_url)
        if not resp:
            continue
        sub_soup = BeautifulSoup(resp.text, "lxml-xml")
        for loc in sub_soup.find_all("loc"):
            url = loc.text
            # Only keep /wiki/ article pages
            if WIKI_PREFIX in url:
                slug = url.split(WIKI_PREFIX, 1)[1]
                if not any(slug.startswith(p) for p in SKIP_PREFIXES):
                    all_urls.append(slug)

    log.info(f"Discovered {len(all_urls)} topic slugs")

    # Save the list
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = METADATA_DIR / "topic_urls.json"
    with open(out_path, "w") as f:
        json.dump({"discovered_at": _now_iso(), "count": len(all_urls), "slugs": sorted(all_urls)}, f, indent=2)
    log.info(f"Saved topic list to {out_path}")
    return all_urls


# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _clean_text(el: Tag) -> str:
    """Extract clean text from an element, preserving list structure."""
    lines: list[str] = []
    for child in el.children:
        if isinstance(child, NavigableString):
            text = child.strip()
            if text:
                lines.append(text)
        elif isinstance(child, Tag):
            if child.name in ("ul", "ol"):
                for li in child.find_all("li", recursive=False):
                    bullet = "- " if child.name == "ul" else ""
                    li_text = li.get_text(separator=" ", strip=True)
                    if li_text:
                        lines.append(f"{bullet}{li_text}")
            elif child.name == "table":
                lines.append(_extract_table_markdown(child))
            elif child.name in ("p", "div", "dd", "dt"):
                text = child.get_text(separator=" ", strip=True)
                if text:
                    lines.append(text)
            elif child.name in ("dl",):
                for item in child.find_all(["dt", "dd"], recursive=False):
                    text = item.get_text(separator=" ", strip=True)
                    if text:
                        prefix = "**" if item.name == "dt" else "  "
                        suffix = "**" if item.name == "dt" else ""
                        lines.append(f"{prefix}{text}{suffix}")
            else:
                text = child.get_text(separator=" ", strip=True)
                if text:
                    lines.append(text)
    return "\n".join(lines)


def _extract_table_markdown(table: Tag) -> str:
    """Convert an HTML table to markdown."""
    rows = table.find_all("tr")
    if not rows:
        return ""

    md_rows: list[str] = []
    for i, row in enumerate(rows):
        cells = row.find_all(["th", "td"])
        cell_texts = [c.get_text(separator=" ", strip=True) for c in cells]
        md_rows.append("| " + " | ".join(cell_texts) + " |")
        if i == 0:
            md_rows.append("| " + " | ".join(["---"] * len(cell_texts)) + " |")

    return "\n".join(md_rows)


def _extract_images(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Extract image URLs from the article content."""
    images = []
    content_div = soup.find("div", {"id": "mw-content-text"})
    if not content_div:
        return images

    for img in content_div.find_all("img"):
        src = img.get("src", "")
        if not src or "skins/" in src or "resources/" in src:
            continue
        # Skip tiny icons / UI elements
        width = img.get("width")
        if width and int(width) < 50:
            continue

        full_url = urljoin(base_url, src)
        alt = img.get("alt", "")
        images.append({"url": full_url, "alt": alt})

    return images


def _extract_categories(soup: BeautifulSoup) -> list[str]:
    """Extract category names from the page."""
    cats = []
    cat_links = soup.find("div", {"id": "catlinks"})
    if cat_links:
        for a in cat_links.find_all("a"):
            href = a.get("href", "")
            if "Category:" in href:
                cats.append(a.get_text(strip=True))
    return cats


def _extract_see_also(soup: BeautifulSoup) -> list[str]:
    """Extract 'See Also' links as topic slugs."""
    links = []
    # Find the See Also heading
    for heading in soup.find_all(["h2", "h3"]):
        heading_text = heading.get_text(strip=True)
        if "see also" in heading_text.lower():
            # Get the next sibling(s) until the next heading
            sibling = heading.find_next_sibling()
            while sibling and sibling.name not in ("h2", "h3"):
                for a in sibling.find_all("a") if isinstance(sibling, Tag) else []:
                    href = a.get("href", "")
                    if WIKI_PREFIX in href:
                        slug = href.split(WIKI_PREFIX, 1)[1]
                        if not any(slug.startswith(p) for p in SKIP_PREFIXES):
                            links.append(unquote(slug))
                sibling = sibling.find_next_sibling() if sibling else None
            break
    return links


def extract_page(slug: str) -> dict | None:
    """
    Fetch and extract structured content from a single WikEM topic page.
    Returns a dict with title, sections, images, categories, etc.
    """
    url = f"{BASE_URL}{WIKI_PREFIX}{slug}"
    log.info(f"Scraping: {url}")

    resp = fetch(url)
    if not resp:
        return None

    html = resp.text
    soup = BeautifulSoup(html, "lxml")

    # --- Save raw HTML ---
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"{slug.replace('/', '_')}.html"
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(html)

    # --- Title ---
    title_el = soup.find("h1", {"id": "firstHeading"})
    title = title_el.get_text(strip=True) if title_el else unquote(slug)

    # --- Content body ---
    content_div = soup.find("div", {"id": "mw-content-text"})
    if not content_div:
        log.warning(f"No content div found for {slug}")
        return None

    # --- Extract sections ---
    sections: list[dict] = []
    current_heading = "Introduction"
    current_level = 2
    current_content_parts: list[str] = []

    def _flush_section():
        text = "\n".join(current_content_parts).strip()
        if text:
            sections.append({
                "heading": current_heading,
                "level": current_level,
                "content": text,
                "order": len(sections) + 1,
            })

    # Walk through direct children of the parser output div
    parser_output = content_div.find("div", class_="mw-parser-output")
    if not parser_output:
        parser_output = content_div

    for child in parser_output.children:
        if not isinstance(child, Tag):
            continue

        # Heading → flush previous section, start new one
        if child.name in ("h2", "h3", "h4"):
            _flush_section()
            current_heading = child.get_text(strip=True)
            # Remove [edit] link text
            current_heading = re.sub(r"\[edit\]", "", current_heading).strip()
            current_level = int(child.name[1])
            current_content_parts = []
        else:
            text = _clean_text(child) if child.name != "div" or "toc" not in child.get("class", []) else ""
            if text:
                current_content_parts.append(text)

    # Flush last section
    _flush_section()

    # --- Images ---
    images = _extract_images(soup, url)

    # --- Categories ---
    categories = _extract_categories(soup)

    # --- See Also ---
    see_also = _extract_see_also(soup)

    # --- Build result ---
    full_text = "\n\n".join(s["content"] for s in sections)
    result = {
        "slug": slug,
        "url": url,
        "title": title,
        "last_scraped": _now_iso(),
        "content_hash": _content_hash(full_text),
        "sections": sections,
        "images": images,
        "categories": categories,
        "see_also": see_also,
    }

    # --- Save processed JSON ---
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    json_path = PROCESSED_DIR / f"{slug.replace('/', '_')}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # --- Save as Markdown (for RAG indexing) ---
    md_path = PROCESSED_DIR / f"{slug.replace('/', '_')}.md"
    md_lines = [
        f"# {title}",
        f"",
        f"Source: [WikEM]({url}) (CC BY-SA 3.0)",
        f"Categories: {', '.join(categories) if categories else 'N/A'}",
        f"",
    ]
    for section in sections:
        prefix = "#" * section["level"]
        md_lines.append(f"{prefix} {section['heading']}")
        md_lines.append("")
        md_lines.append(section["content"])
        md_lines.append("")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    log.info(
        f"  ✅ {title}: {len(sections)} sections, "
        f"{len(images)} images, {len(categories)} categories"
    )
    return result


# ---------------------------------------------------------------------------
# Batch scraping
# ---------------------------------------------------------------------------

def scrape_topics(slugs: list[str], skip_existing: bool = True) -> dict:
    """Scrape a list of topics, returning summary stats."""
    stats = {"total": len(slugs), "scraped": 0, "skipped": 0, "errors": 0}
    errors: list[dict] = []

    for i, slug in enumerate(slugs, 1):
        log.info(f"[{i}/{len(slugs)}] {slug}")

        # Skip if already scraped and unchanged
        json_path = PROCESSED_DIR / f"{slug.replace('/', '_')}.json"
        if skip_existing and json_path.exists():
            log.info(f"  ⏭ Already exists, skipping")
            stats["skipped"] += 1
            continue

        result = extract_page(slug)
        if result:
            stats["scraped"] += 1
        else:
            stats["errors"] += 1
            errors.append({"slug": slug, "time": _now_iso()})

    # Save error log
    if errors:
        METADATA_DIR.mkdir(parents=True, exist_ok=True)
        err_path = METADATA_DIR / "scrape_errors.json"
        with open(err_path, "w") as f:
            json.dump(errors, f, indent=2)

    # Save scrape log
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    log_path = METADATA_DIR / "scrape_log.json"
    log_data = {
        "last_run": _now_iso(),
        "stats": stats,
    }
    with open(log_path, "w") as f:
        json.dump(log_data, f, indent=2)

    log.info(f"Done! {stats}")
    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="WikEM Scraper")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--test", action="store_true", help="Test with Hyponatremia page")
    group.add_argument("--topic", type=str, help="Scrape a specific topic slug")
    group.add_argument("--discover", action="store_true", help="Discover all topic URLs from sitemap")
    group.add_argument("--all", action="store_true", help="Scrape all discovered topics")
    parser.add_argument("--force", action="store_true", help="Re-scrape even if already exists")

    args = parser.parse_args()

    if args.test:
        result = extract_page("Hyponatremia")
        if result:
            print(f"\n{'='*60}")
            print(f"Title: {result['title']}")
            print(f"URL: {result['url']}")
            print(f"Sections: {len(result['sections'])}")
            for s in result["sections"]:
                preview = s["content"][:80].replace("\n", " ")
                print(f"  {'  ' * (s['level'] - 2)}[{s['order']}] {s['heading']}: {preview}...")
            print(f"Images: {len(result['images'])}")
            for img in result["images"]:
                print(f"  📸 {img['alt'] or img['url']}")
            print(f"Categories: {result['categories']}")
            print(f"See Also: {result['see_also']}")
            print(f"Content Hash: {result['content_hash']}")
            print(f"\nFiles saved to: {OUTPUT_DIR}")
        else:
            print("❌ Failed to scrape test page")

    elif args.topic:
        extract_page(args.topic)

    elif args.discover:
        slugs = discover_topic_urls()
        print(f"\nDiscovered {len(slugs)} topics")

    elif args.all:
        urls_path = METADATA_DIR / "topic_urls.json"
        if not urls_path.exists():
            log.error("No topic_urls.json found. Run --discover first.")
            return
        with open(urls_path) as f:
            data = json.load(f)
        scrape_topics(data["slugs"], skip_existing=not args.force)


if __name__ == "__main__":
    main()
