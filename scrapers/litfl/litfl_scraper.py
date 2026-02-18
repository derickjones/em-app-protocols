#!/usr/bin/env python3
"""
LITFL Scraper — Life in the Fast Lane (litfl.com)
Scrapes LITFL pages and extracts structured content with images.

Content is licensed CC BY-NC-SA 4.0. Attribution is preserved in all outputs.

Usage:
    # Test with a single page
    python litfl_scraper.py --test

    # Scrape a specific page by slug
    python litfl_scraper.py --topic etomidate

    # Scrape a specific page by full URL
    python litfl_scraper.py --url https://litfl.com/etomidate/

    # Discover all URLs from sitemaps
    python litfl_scraper.py --discover
"""

import argparse
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from google.cloud import storage as gcs

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "https://litfl.com"
SITEMAP_INDEX_URL = "https://litfl.com/sitemap_index.xml"

OUTPUT_DIR = Path(__file__).parent / "output"
RAW_DIR = OUTPUT_DIR / "raw"
PROCESSED_DIR = OUTPUT_DIR / "processed"
METADATA_DIR = OUTPUT_DIR / "metadata"

GCS_BUCKET_NAME = os.environ.get("LITFL_BUCKET", "clinical-assistant-457902-litfl")

REQUEST_DELAY = 1.5  # seconds between requests
USER_AGENT = (
    "EmergencyMedicineApp/1.0 "
    "(educational medical reference; contact: derickdavidjones@gmail.com)"
)

# Images to always filter out (logos, icons, ads)
FILTER_IMAGE_URLS = [
    "LITFL-Life-in-the-FastLane-760-180",
    "google-web-search-256x256",
    "gravatar.com",
    "medmastery",
    "advads",
    "cropped-LITFL-Logo-Square",
]

# CSS classes for elements to strip before extraction
STRIP_CLASSES = [
    "m-a-box",                  # Author bio box
    "litfl-medmastery",         # Medmastery ad block
    "wp-block-cover",           # Decorative CTA banners (CCC-700-6, etc.)
    "gb-block-cta",             # Genesis Blocks CTA banners
    "comment-respond",          # Comment form
    "comments-area",            # Comments section
    "sharedaddy",               # Social sharing buttons
    "jp-relatedposts",          # Jetpack related posts
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("litfl")

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

session = requests.Session()
session.headers.update({
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
})


def fetch(url: str) -> requests.Response | None:
    """GET a URL with rate limiting and error handling."""
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        time.sleep(REQUEST_DELAY)
        return resp
    except requests.RequestException as e:
        log.error(f"Failed to fetch {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _slug_from_url(url: str) -> str:
    """Extract slug from a LITFL URL.  https://litfl.com/etomidate/ → etomidate"""
    path = urlparse(url).path.strip("/")
    # Remove trailing slash and any query params
    return path.split("?")[0] if path else ""


def _safe_filename(slug: str) -> str:
    """Convert a slug to a safe filename."""
    return slug.replace("/", "_").replace(" ", "_")


# ---------------------------------------------------------------------------
# Metadata extraction (Yoast JSON-LD)
# ---------------------------------------------------------------------------

def _extract_yoast_metadata(soup: BeautifulSoup) -> dict:
    """Extract structured metadata from Yoast JSON-LD schema."""
    meta = {
        "author": None,
        "date_published": None,
        "date_modified": None,
        "description": None,
        "word_count": None,
        "article_sections": [],
        "keywords": [],
    }

    script_tag = soup.find("script", class_="yoast-schema-graph")
    if not script_tag or not script_tag.string:
        return meta

    try:
        schema = json.loads(script_tag.string)
        raw_graph = schema.get("@graph", [])

        # Flatten: some items in @graph can be nested lists (e.g. Person wrapped in [])
        graph = []
        for entry in raw_graph:
            if isinstance(entry, list):
                graph.extend(entry)
            else:
                graph.append(entry)

        for item in graph:
            if not isinstance(item, dict):
                continue
            raw_type = item.get("@type", "")
            # @type can be a string or a list (e.g. ["Article", "MedicalWebPage"])
            if isinstance(raw_type, list):
                item_types = raw_type
            else:
                item_types = [raw_type]

            if "Article" in item_types or "MedicalWebPage" in item_types:
                author_field = item.get("author", {})
                if isinstance(author_field, dict):
                    meta["author"] = author_field.get("name")
                elif isinstance(author_field, list) and author_field:
                    meta["author"] = author_field[0].get("name") if isinstance(author_field[0], dict) else None
                meta["date_published"] = item.get("datePublished")
                meta["date_modified"] = item.get("dateModified")
                meta["word_count"] = item.get("wordCount")
                meta["keywords"] = item.get("keywords", [])
                meta["article_sections"] = item.get("articleSection", [])
                if isinstance(meta["article_sections"], str):
                    meta["article_sections"] = [meta["article_sections"]]

            elif "WebPage" in item_types:
                if not meta["description"]:
                    meta["description"] = item.get("description")
                if not meta["date_published"]:
                    meta["date_published"] = item.get("datePublished")
                if not meta["date_modified"]:
                    meta["date_modified"] = item.get("dateModified")

            elif "Person" in item_types:
                if not meta["author"]:
                    meta["author"] = item.get("name")

    except (json.JSONDecodeError, KeyError) as e:
        log.warning(f"Failed to parse Yoast JSON-LD: {e}")

    return meta


# ---------------------------------------------------------------------------
# Article metadata from HTML
# ---------------------------------------------------------------------------

def _extract_html_metadata(soup: BeautifulSoup) -> dict:
    """Extract metadata from the HTML article tag and header elements."""
    meta = {
        "title": None,
        "author": None,
        "date": None,
        "categories": [],
        "tags": [],
    }

    # Title from <h1 class="page-title"> or <h3 class="page-title">
    title_el = soup.find(["h1", "h3"], class_="page-title")
    if title_el:
        meta["title"] = title_el.get_text(strip=True)

    # Author from ct-meta-element-author
    author_el = soup.find("a", class_="ct-meta-element-author")
    if author_el:
        span = author_el.find("span")
        meta["author"] = span.get_text(strip=True) if span else author_el.get_text(strip=True)

    # Date from ct-meta-element-date
    date_el = soup.find("time", class_="ct-meta-element-date")
    if date_el:
        meta["date"] = date_el.get("datetime")

    # Categories and tags from <article> class attribute
    article_el = soup.find("article")
    if article_el:
        classes = article_el.get("class", [])
        for cls in classes:
            if cls.startswith("category-"):
                meta["categories"].append(cls.replace("category-", "").replace("-", " ").title())
            elif cls.startswith("tag-"):
                meta["tags"].append(cls.replace("tag-", "").replace("-", " "))

    return meta


# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------

def _get_content_div(soup: BeautifulSoup) -> Tag | None:
    """
    Find the main content div.
    LITFL pages have 2 entry-content divs:
      1st = header search bar (in off-canvas/header)
      2nd = actual article content
    We want the one that is a child of <article> or the 2nd one.
    """
    # Prefer the entry-content inside <article>
    article = soup.find("article")
    if article:
        content = article.find("div", class_="entry-content")
        if content:
            return content

    # Fallback: get all entry-content divs and take the last substantial one
    all_content = soup.find_all("div", class_="entry-content")
    for div in reversed(all_content):
        # Skip tiny divs (like the header search bar)
        if len(div.get_text(strip=True)) > 100:
            return div

    return None


def _strip_noise(content_div: Tag) -> None:
    """Remove non-content elements from the content div (in-place)."""
    # Remove noscript tags (duplicate lazy-loaded images)
    for noscript in content_div.find_all("noscript"):
        noscript.decompose()

    # Remove elements by class
    for cls in STRIP_CLASSES:
        for el in content_div.find_all(class_=lambda c: c and cls in " ".join(c) if isinstance(c, list) else cls in (c or "")):
            el.decompose()

    # Remove ad divs with litfl-target or advads classes
    for el in content_div.find_all(class_=lambda c: c and any(
        x in " ".join(c) if isinstance(c, list) else x in (c or "")
        for x in ["advads", "litfl-target"]
    )):
        el.decompose()


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
            elif child.name == "blockquote":
                bq_text = child.get_text(separator=" ", strip=True)
                if bq_text:
                    lines.append(f"> {bq_text}")
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
            elif child.name == "figure":
                # Skip figures (handled separately in image extraction)
                pass
            elif child.name in ("h2", "h3", "h4", "h5", "h6"):
                # Skip headings (handled in section extraction)
                pass
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


def _extract_sections(content_div: Tag) -> list[dict]:
    """
    Extract sections by walking through content div children.
    LITFL uses h2-h6 with class wp-block-heading for sections.
    Some pages have no headings at all — treat as single section.
    """
    sections: list[dict] = []
    current_heading = "Introduction"
    current_level = 2
    current_parts: list[str] = []

    def _flush():
        text = "\n".join(current_parts).strip()
        if text:
            sections.append({
                "heading": current_heading,
                "level": current_level,
                "content": text,
                "order": len(sections) + 1,
            })

    for child in content_div.children:
        if not isinstance(child, Tag):
            # Capture loose text nodes
            text = child.strip() if isinstance(child, NavigableString) else ""
            if text:
                current_parts.append(text)
            continue

        # Heading → flush previous section, start new one
        if child.name in ("h2", "h3", "h4", "h5", "h6"):
            _flush()
            heading_text = child.get_text(strip=True)
            # Some headings wrap text in <strong>
            heading_text = re.sub(r"\s+", " ", heading_text).strip()
            if heading_text:
                current_heading = heading_text
                current_level = int(child.name[1])
                current_parts = []
        elif child.name == "figure":
            # Skip figures (images handled separately)
            # But extract figcaption text as content
            figcaption = child.find("figcaption")
            if figcaption:
                caption_text = figcaption.get_text(separator=" ", strip=True)
                if caption_text:
                    current_parts.append(f"[Image: {caption_text}]")
        else:
            text = _clean_text(child)
            if text:
                current_parts.append(text)

    _flush()
    return sections


# ---------------------------------------------------------------------------
# Image extraction
# ---------------------------------------------------------------------------

def _should_filter_image(url: str) -> bool:
    """Check if an image URL should be filtered out (logos, ads, icons)."""
    if not url:
        return True
    for pattern in FILTER_IMAGE_URLS:
        if pattern in url:
            return True
    # Filter SVG placeholder data URIs
    if url.startswith("data:image/svg+xml"):
        return True
    return False


def _get_image_url(img_tag: Tag) -> str | None:
    """
    Get the best image URL from an <img> tag.
    Priority: data-orig-file → data-lazy-src → src
    Skip SVG placeholders.
    """
    # data-orig-file = full resolution original
    url = img_tag.get("data-orig-file")
    if url and not _should_filter_image(url):
        return url

    # data-lazy-src = lazy loaded (usually full or large size)
    url = img_tag.get("data-lazy-src")
    if url and not _should_filter_image(url):
        return url

    # src = direct source (but skip SVG placeholders)
    url = img_tag.get("src")
    if url and not url.startswith("data:") and not _should_filter_image(url):
        return url

    return None


def _extract_images(content_div: Tag) -> list[dict]:
    """
    Extract content images from figure.wp-block-image elements.
    Associates each image with the nearest preceding section heading.
    """
    images = []
    current_section = "Introduction"

    for child in content_div.children:
        if not isinstance(child, Tag):
            continue

        # Track section headings
        if child.name in ("h2", "h3", "h4", "h5", "h6"):
            heading_text = child.get_text(strip=True)
            heading_text = re.sub(r"\s+", " ", heading_text).strip()
            if heading_text:
                current_section = heading_text

        # Extract images from figure.wp-block-image OR div.wp-block-image > figure
        figures = []
        if child.name == "figure" and child.get("class") and "wp-block-image" in " ".join(child.get("class", [])):
            figures.append(child)
        elif child.name == "div" and child.get("class") and "wp-block-image" in " ".join(child.get("class", [])):
            # Pattern: <div class="wp-block-image"><figure class="aligncenter">
            inner_fig = child.find("figure")
            if inner_fig:
                figures.append(inner_fig)
            elif child.find("img"):
                # Rare: img directly inside div.wp-block-image without figure
                figures.append(child)
        else:
            # Also search nested figures (e.g., inside deeper divs)
            for nested_div in child.find_all("div", class_=lambda c: c and "wp-block-image" in (" ".join(c) if isinstance(c, list) else (c or ""))):
                inner_fig = nested_div.find("figure")
                if inner_fig:
                    figures.append(inner_fig)
                elif nested_div.find("img"):
                    figures.append(nested_div)
            # Original: figure.wp-block-image nested inside other elements
            figures.extend(child.find_all("figure", class_=lambda c: c and "wp-block-image" in (" ".join(c) if isinstance(c, list) else (c or ""))))

        for figure in figures:
            img = figure.find("img")
            if not img:
                continue

            url = _get_image_url(img)
            if not url:
                continue

            # Skip tiny icons (width < 50px)
            width = img.get("width")
            if width:
                try:
                    if int(width) < 50:
                        continue
                except (ValueError, TypeError):
                    pass

            # Get image metadata
            alt = img.get("alt", "")
            title = img.get("data-image-title", "")
            title = unescape(title) if title else ""

            # Get figcaption
            figcaption = figure.find("figcaption")
            caption = ""
            if figcaption:
                caption = figcaption.get_text(separator=" ", strip=True)

            # Derive a label: prefer title → alt → filename
            label = title or alt or url.split("/")[-1].rsplit(".", 1)[0].replace("-", " ")

            images.append({
                "url": url,
                "alt": alt,
                "title": title,
                "caption": caption,
                "label": label,
                "section": current_section,
                "filename": url.split("/")[-1] if "/" in url else "",
            })

    return images


# ---------------------------------------------------------------------------
# GCS upload
# ---------------------------------------------------------------------------

def _download_images_to_gcs(slug: str, images: list[dict]) -> list[dict]:
    """Download content images to GCS bucket. Returns updated image list."""
    if not images:
        return images

    try:
        client = gcs.Client()
        bucket = client.bucket(GCS_BUCKET_NAME)
    except Exception as e:
        log.error(f"Failed to connect to GCS bucket {GCS_BUCKET_NAME}: {e}")
        return images

    safe_slug = _safe_filename(slug)
    updated = []

    for img in images:
        original_url = img["url"]
        filename = img.get("filename") or original_url.split("/")[-1]
        gcs_path = f"images/{safe_slug}/{filename}"

        try:
            resp = session.get(original_url, timeout=15)
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "image/png")

            blob = bucket.blob(gcs_path)
            blob.upload_from_string(resp.content, content_type=content_type)
            blob.make_public()

            gcs_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{gcs_path}"

            updated.append({
                **img,
                "url": gcs_url,
                "original_url": original_url,
                "gcs_path": gcs_path,
            })
            log.info(f"  📸 {filename} → {gcs_path}")
            time.sleep(0.3)

        except Exception as e:
            log.warning(f"  ⚠️ Failed to download {original_url}: {e}")
            updated.append({
                **img,
                "original_url": original_url,
                "gcs_path": None,
            })

    return updated


def _upload_metadata_to_gcs(slug: str, title: str, images: list[dict]):
    """Upload image metadata JSON to GCS for API image lookup."""
    try:
        client = gcs.Client()
        bucket = client.bucket(GCS_BUCKET_NAME)

        safe_slug = _safe_filename(slug)
        metadata = {
            "protocol_id": slug,
            "title": title,
            "source": "litfl",
            "license": "CC BY-NC-SA 4.0",
            "images": [
                {
                    "url": img["url"],
                    "alt": img.get("alt", ""),
                    "label": img.get("label", ""),
                    "caption": img.get("caption", ""),
                    "section": img.get("section", ""),
                    "page": i,
                }
                for i, img in enumerate(images)
                if img.get("url")
            ],
        }

        blob = bucket.blob(f"metadata/{safe_slug}.json")
        blob.upload_from_string(
            json.dumps(metadata, indent=2),
            content_type="application/json",
        )
        log.info(f"  📋 Metadata uploaded: metadata/{safe_slug}.json ({len(images)} images)")
    except Exception as e:
        log.warning(f"  ⚠️ Failed to upload metadata for {slug}: {e}")


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def extract_page(slug: str, upload_gcs: bool = True) -> dict | None:
    """
    Fetch and extract structured content from a single LITFL page.
    Returns a dict with title, sections, images, metadata, etc.
    """
    url = f"{BASE_URL}/{slug}/"
    log.info(f"Scraping: {url}")

    resp = fetch(url)
    if not resp:
        return None

    # Check for 404 / redirect to search
    if resp.status_code == 404:
        log.warning(f"  404: {url}")
        return None

    html = resp.text
    soup = BeautifulSoup(html, "lxml")

    # Detect 404 pages (LITFL returns 200 with "Oops" message)
    oops = soup.find("h1", class_="page-title")
    if oops and "can't be found" in oops.get_text().lower():
        log.warning(f"  Soft 404: {url}")
        return None

    # --- Save raw HTML ---
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    safe_slug = _safe_filename(slug)
    raw_path = RAW_DIR / f"{safe_slug}.html"
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(html)

    # --- Extract metadata ---
    yoast_meta = _extract_yoast_metadata(soup)
    html_meta = _extract_html_metadata(soup)

    title = html_meta["title"] or slug.replace("-", " ").title()
    author = html_meta["author"] or yoast_meta["author"] or "Unknown"
    categories = html_meta["categories"]
    tags = html_meta["tags"]
    date_modified = html_meta["date"] or yoast_meta["date_modified"]

    # --- Content div ---
    content_div = _get_content_div(soup)
    if not content_div:
        log.warning(f"  No content div found for {slug}")
        return None

    # --- Strip noise ---
    _strip_noise(content_div)

    # --- Extract images (before section extraction, as both walk the DOM) ---
    images = _extract_images(content_div)

    # --- Extract sections ---
    sections = _extract_sections(content_div)

    if not sections:
        log.warning(f"  No content extracted for {slug}")
        return None

    # --- Download images to GCS ---
    if upload_gcs and images:
        images = _download_images_to_gcs(slug, images)

    # --- Build result ---
    full_text = "\n\n".join(s["content"] for s in sections)
    result = {
        "slug": slug,
        "url": url,
        "title": title,
        "author": author,
        "date_modified": date_modified,
        "last_scraped": _now_iso(),
        "content_hash": _content_hash(full_text),
        "description": yoast_meta["description"],
        "categories": categories,
        "tags": tags,
        "article_sections": yoast_meta["article_sections"],
        "word_count": yoast_meta["word_count"],
        "license": "CC BY-NC-SA 4.0",
        "attribution": f"Content from Life in the Fast Lane (LITFL) — {url} — by {author}. Licensed under CC BY-NC-SA 4.0.",
        "sections": sections,
        "images": [
            {
                "url": img.get("url", img.get("original_url", "")),
                "alt": img.get("alt", ""),
                "label": img.get("label", ""),
                "caption": img.get("caption", ""),
                "section": img.get("section", ""),
                "gcs_path": img.get("gcs_path"),
            }
            for img in images
        ],
    }

    # --- Save processed JSON ---
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    json_path = PROCESSED_DIR / f"{safe_slug}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # --- Save as Markdown (for RAG indexing) ---
    md_path = PROCESSED_DIR / f"{safe_slug}.md"
    md_lines = [
        f"# {title}",
        "",
        f"Source: [LITFL]({url}) by {author} (CC BY-NC-SA 4.0)",
        f"Categories: {', '.join(categories) if categories else 'N/A'}",
        "",
    ]
    for section in sections:
        prefix = "#" * min(section["level"], 6)
        md_lines.append(f"{prefix} {section['heading']}")
        md_lines.append("")
        md_lines.append(section["content"])
        md_lines.append("")
    md_lines.append("---")
    md_lines.append(f"*Content from [LITFL]({url}) by {author}. Licensed under CC BY-NC-SA 4.0.*")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    # --- Upload metadata to GCS ---
    if upload_gcs:
        _upload_metadata_to_gcs(slug, title, images)

    log.info(
        f"  ✅ {title}: {len(sections)} sections, "
        f"{len(images)} images, {len(categories)} categories"
    )
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LITFL Scraper")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--test", action="store_true", help="Test with etomidate page")
    group.add_argument("--topic", type=str, help="Scrape a specific topic slug")
    group.add_argument("--url", type=str, help="Scrape a specific full URL")
    group.add_argument("--multi", nargs="+", help="Scrape multiple slugs")
    parser.add_argument("--no-gcs", action="store_true", help="Skip GCS upload (local only)")

    args = parser.parse_args()

    upload_gcs = not args.no_gcs

    if args.test:
        # Test with a few representative pages
        test_slugs = [
            "etomidate",
            "left-bundle-branch-block-lbbb-ecg-library",
            "digoxin-toxicity-ccc",
        ]
        for slug in test_slugs:
            print(f"\n{'='*70}")
            print(f"Testing: {slug}")
            print(f"{'='*70}")
            result = extract_page(slug, upload_gcs=upload_gcs)
            if result:
                print(f"  Title:      {result['title']}")
                print(f"  Author:     {result['author']}")
                print(f"  Categories: {result['categories']}")
                print(f"  Tags:       {result['tags'][:5]}{'...' if len(result['tags']) > 5 else ''}")
                print(f"  Sections:   {len(result['sections'])}")
                for s in result["sections"]:
                    preview = s["content"][:60].replace("\n", " ")
                    indent = "  " * (s["level"] - 2)
                    print(f"    {indent}[{s['order']}] {s['heading']}: {preview}...")
                print(f"  Images:     {len(result['images'])}")
                for img in result["images"]:
                    print(f"    📸 [{img['section']}] {img['label']}")
                    if img.get("caption"):
                        print(f"       Caption: {img['caption'][:80]}...")
                print(f"  Word count: {result.get('word_count', 'N/A')}")
                print(f"  License:    {result['license']}")
            else:
                print("  ❌ Failed to scrape")

    elif args.topic:
        result = extract_page(args.topic, upload_gcs=upload_gcs)
        if result:
            print(f"\n✅ Scraped: {result['title']} ({len(result['sections'])} sections, {len(result['images'])} images)")
        else:
            print("❌ Failed to scrape")

    elif args.url:
        slug = _slug_from_url(args.url)
        if slug:
            result = extract_page(slug, upload_gcs=upload_gcs)
            if result:
                print(f"\n✅ Scraped: {result['title']} ({len(result['sections'])} sections, {len(result['images'])} images)")
            else:
                print("❌ Failed to scrape")
        else:
            print(f"❌ Could not extract slug from URL: {args.url}")

    elif args.multi:
        for slug in args.multi:
            result = extract_page(slug, upload_gcs=upload_gcs)
            if result:
                print(f"✅ {result['title']}: {len(result['sections'])} sections, {len(result['images'])} images")
            else:
                print(f"❌ Failed: {slug}")


if __name__ == "__main__":
    main()
