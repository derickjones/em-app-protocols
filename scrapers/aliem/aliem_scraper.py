#!/usr/bin/env python3
"""
ALiEM Scraper — aliem.com (Track A: PV Cards + MEdIC Series)
Scrapes CC BY-NC-ND 3.0 licensed content from ALiEM.

ALiEM uses a SPLIT LICENSE:
  - PV Cards + MEdIC Series: CC BY-NC-ND 3.0 (Track A — this scraper)
  - All other content: "All Rights Reserved" (Track B — requires permission)

Usage:
    python aliem_scraper.py --test
    python aliem_scraper.py --topic paucis-verbis-hyperkalemia-management
    python aliem_scraper.py --url https://www.aliem.com/paucis-verbis-hyperkalemia-management/
    python aliem_scraper.py --test --no-gcs
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
from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from google.cloud import storage as gcs

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "https://www.aliem.com"
SITEMAP_INDEX_URL = "https://www.aliem.com/sitemap_index.xml"

OUTPUT_DIR = Path(__file__).parent / "output"
RAW_DIR = OUTPUT_DIR / "raw"
PROCESSED_DIR = OUTPUT_DIR / "processed"
METADATA_DIR = OUTPUT_DIR / "metadata"

GCS_BUCKET_NAME = os.environ.get("ALIEM_BUCKET", "clinical-assistant-457902-aliem")

# No Crawl-delay in robots.txt, but Cloudflare protection — be polite
REQUEST_DELAY = 5.0
USER_AGENT = (
    "EmergencyMedicineApp/1.0 "
    "(educational medical reference; contact: derickdavidjones@gmail.com)"
)

# Images to always filter out (logos, icons, ads, avatars)
FILTER_IMAGE_URLS = [
    "gravatar.com",
    "aliem-logo",
    "cropped-aliem",
    "tricks-of-trade-book",
    "advertisement",
    "sponsor",
    "favicon",
    "aliemcards.com",
    "wp-content/themes",
    "site-logo",
    "amazon",
    "rss-icon",
    "facebook-icon",
    "twitter-icon",
    "instagram-icon",
]

# CSS classes for elements to strip before extraction
STRIP_CLASSES = [
    "sharedaddy",               # Social sharing buttons
    "sd-content",               # Sharing content container
    "sd-block",                 # Sharing block
    "jp-relatedposts",          # Jetpack related posts
    "post-navigation",          # Previous/Next navigation
    "comments-area",            # Comments section
    "comment-respond",          # Comment form
    "author-box",               # Author bio box
    "author-info",              # Author info section
    "entry-footer",             # Footer metadata
    "widget-area",              # Sidebar widgets
    "site-footer",              # Site footer
    "nav-links",                # Navigation links
    "post-nav-links",           # Post nav links
]

STRIP_IDS = [
    "comments",
    "respond",
]

# Content end markers — stop extraction when these are found
CONTENT_END_MARKERS = [
    "Share This",
    "Click to share on",
    "Bio Twitter",
    "Bio Twitter Facebook",
    "Latest Posts",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("aliem")

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

session = requests.Session()
session.headers.update({
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
})


def fetch(url: str, delay: float = REQUEST_DELAY) -> requests.Response | None:
    """GET a URL with rate limiting and error handling."""
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        time.sleep(delay)
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
    """Extract slug from an ALiEM URL.
    https://www.aliem.com/paucis-verbis-hyperkalemia-management/  →  paucis-verbis-hyperkalemia-management
    """
    path = urlparse(url).path.strip("/")
    return path.split("?")[0] if path else ""


def _safe_filename(slug: str) -> str:
    """Convert a slug to a safe filename."""
    return slug.replace("/", "_").replace(" ", "_")


def _is_track_a(slug: str) -> bool:
    """Check if this slug is Track A (CC licensed)."""
    slug_lower = slug.lower()
    pv_patterns = ["paucis-verbis-", "pv-card-", "pv-", "tox-meds-pv-cards"]
    medic_patterns = ["medic-series-", "medic-case-", "medic-"]
    for p in pv_patterns:
        if p in slug_lower:
            return True
    for p in medic_patterns:
        if p in slug_lower:
            return True
    return False


def _get_track_a_type(slug: str) -> str:
    """Return PV Card or MEdIC type."""
    slug_lower = slug.lower()
    for p in ["paucis-verbis-", "pv-card-", "pv-", "tox-meds-pv-cards"]:
        if p in slug_lower:
            return "pv_card"
    return "medic"


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

        # Flatten nested lists
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
            if isinstance(raw_type, list):
                item_types = raw_type
            else:
                item_types = [raw_type]

            if any(t in item_types for t in ("Article", "MedicalWebPage", "BlogPosting")):
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
    """Extract metadata from ALiEM HTML article elements."""
    meta = {
        "title": None,
        "author": None,
        "date": None,
        "categories": [],
        "tags": [],
    }

    # Title from <h1>
    title_el = soup.find("h1", class_="entry-title")
    if not title_el:
        title_el = soup.find("h1")
    if title_el:
        meta["title"] = title_el.get_text(strip=True)

    # Categories from article footer or entry-meta (NOT site-wide nav)
    # Look for category links inside the article's metadata areas
    article_el = soup.find("article")
    cat_containers = []
    if article_el:
        cat_containers = article_el.find_all(class_=lambda c: c and any(
            k in (" ".join(c) if isinstance(c, list) else (c or ""))
            for k in ("cat-links", "entry-categories", "entry-meta", "entry-footer", "post-categories")
        ))
    # Fallback: Yoast article_sections
    if not cat_containers:
        # Use Yoast articleSection if available (populated later from JSON-LD)
        pass
    for container in cat_containers:
        for a in container.find_all("a", href=True):
            href = a.get("href", "")
            if "/category/" in href:
                cat = a.get_text(strip=True)
                if cat and cat not in meta["categories"] and len(cat) < 100:
                    meta["categories"].append(cat)
            elif "/tag/" in href:
                tag = a.get_text(strip=True)
                if tag and tag not in meta["tags"] and len(tag) < 100:
                    meta["tags"].append(tag)

    # Date from time element or meta
    time_el = soup.find("time")
    if time_el:
        meta["date"] = time_el.get("datetime")
    if not meta["date"]:
        og_time = soup.find("meta", property="article:published_time")
        if og_time:
            meta["date"] = og_time.get("content")

    # Author from byline
    author_el = soup.find(class_="author")
    if author_el:
        a_tag = author_el.find("a")
        if a_tag:
            meta["author"] = a_tag.get_text(strip=True)
        else:
            meta["author"] = author_el.get_text(strip=True)

    return meta


# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------

def _get_content_div(soup: BeautifulSoup) -> Tag | None:
    """
    Find the main content div.
    ALiEM uses standard WordPress with entry-content inside <article>.
    """
    # Primary: entry-content inside <article>
    article = soup.find("article")
    if article:
        content = article.find("div", class_="entry-content")
        if content and len(content.get_text(strip=True)) > 50:
            return content

    # Fallback: any entry-content div with substantial text
    all_content = soup.find_all("div", class_="entry-content")
    for div in all_content:
        if len(div.get_text(strip=True)) > 50:
            return div

    # Last resort: look for post-content div
    post_content = soup.find("div", class_="post-content")
    if post_content and len(post_content.get_text(strip=True)) > 50:
        return post_content

    return None


def _strip_noise(content_div: Tag) -> None:
    """Remove non-content elements from the content div (in-place)."""
    # Remove noscript tags
    for noscript in content_div.find_all("noscript"):
        noscript.decompose()

    # Remove elements by class
    for cls in STRIP_CLASSES:
        for el in content_div.find_all(class_=lambda c: c and cls in (" ".join(c) if isinstance(c, list) else (c or ""))):
            el.decompose()

    # Remove elements by ID
    for eid in STRIP_IDS:
        el = content_div.find(id=eid)
        if el:
            el.decompose()

    # Remove "Share This" section and everything after
    for el in content_div.find_all(["h3", "h4", "h5", "div", "p"]):
        text = el.get_text(strip=True)
        if text == "Share This" or text.startswith("Click to share on"):
            next_siblings = list(el.find_next_siblings())
            el.decompose()
            for sib in next_siblings:
                if isinstance(sib, Tag):
                    sib.decompose()
            break

    # Remove author bio section at bottom ("Bio Twitter Latest Posts")
    for el in content_div.find_all(["div", "section"]):
        text = el.get_text(strip=True)[:50]
        if "Bio" in text and "Latest Posts" in text:
            el.decompose()
            break

    # Remove MCE editor bookmark spans (TinyMCE artifacts)
    for span in content_div.find_all("span", attrs={"data-mce-type": "bookmark"}):
        span.decompose()
    for span in content_div.find_all("span", class_=lambda c: c and "mce_SELRES" in (" ".join(c) if isinstance(c, list) else (c or ""))):
        span.decompose()

    # Remove HTML comments
    for comment in content_div.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()


def _clean_text(el: Tag) -> str:
    """Extract clean text from an element, preserving list structure."""
    lines: list[str] = []

    for child in el.children:
        if isinstance(child, NavigableString):
            text = child.strip()
            if text:
                # Strip any raw HTML tags that leaked through
                text = re.sub(r"<[^>]+>", "", text).strip()
                if text:
                    lines.append(text)
        elif isinstance(child, Tag):
            # Skip MCE bookmarks and hidden spans
            if child.name == "span" and (
                child.get("data-mce-type") == "bookmark"
                or (child.get("class") and any("mce" in c for c in child.get("class", [])))
                or child.get("style", "").find("display: inline-block; width: 0px") != -1
            ):
                continue
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
                pass  # Images handled separately
            elif child.name in ("h2", "h3", "h4", "h5", "h6"):
                pass  # Headings handled in section extraction
            else:
                text = child.get_text(separator=" ", strip=True)
                if text:
                    # Strip any residual HTML tags
                    text = re.sub(r"<[^>]+>", "", text).strip()
                    if text:
                        lines.append(text)

    result = "\n".join(lines)
    # Final cleanup: strip any remaining HTML tag fragments
    result = re.sub(r"<[^>]+>", "", result)
    return result


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
    ALiEM uses standard h2/h3 headings. PV Cards may have minimal headings.
    """
    sections: list[dict] = []
    current_heading = "Introduction"
    current_level = 2
    current_parts: list[str] = []

    def _flush():
        text = "\n".join(current_parts).strip()
        if text:
            # Check if we've hit a content-end marker
            for marker in CONTENT_END_MARKERS:
                if marker in text:
                    idx = text.index(marker)
                    text = text[:idx].strip()
                    break
            if text:
                sections.append({
                    "heading": current_heading,
                    "level": current_level,
                    "content": text,
                    "order": len(sections) + 1,
                })

    for child in content_div.children:
        if not isinstance(child, Tag):
            text = child.strip() if isinstance(child, NavigableString) else ""
            if text:
                # Check for end markers
                should_stop = False
                for marker in CONTENT_END_MARKERS:
                    if marker in text:
                        should_stop = True
                        break
                if should_stop:
                    break
                current_parts.append(text)
            continue

        # Check for content-end marker
        el_text = child.get_text(strip=True)
        should_stop = False
        for marker in CONTENT_END_MARKERS:
            if el_text.startswith(marker):
                should_stop = True
                break
        if should_stop:
            break

        # Heading → flush previous section, start new one
        if child.name in ("h2", "h3", "h4", "h5", "h6"):
            _flush()
            heading_text = child.get_text(strip=True)
            heading_text = re.sub(r"\s+", " ", heading_text).strip()
            if heading_text:
                current_heading = heading_text
                current_level = int(child.name[1])
                current_parts = []
        elif child.name == "figure":
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
    """Check if an image URL should be filtered out."""
    if not url:
        return True
    for pattern in FILTER_IMAGE_URLS:
        if pattern.lower() in url.lower():
            return True
    if url.startswith("data:image/svg+xml"):
        return True
    return False


def _get_image_url(img_tag: Tag) -> str | None:
    """
    Get the best image URL from an <img> tag.
    ALiEM uses Jetpack CDN (i0.wp.com) — handle these URLs.
    Priority: data-orig-file → data-lazy-src → srcset (largest) → src
    """
    # data-orig-file = full resolution original
    url = img_tag.get("data-orig-file")
    if url and not _should_filter_image(url):
        return url

    # data-lazy-src = lazy loaded
    url = img_tag.get("data-lazy-src")
    if url and not _should_filter_image(url):
        return url

    # srcset — pick the largest image
    srcset = img_tag.get("srcset") or img_tag.get("data-lazy-srcset")
    if srcset:
        best_url = None
        best_width = 0
        for part in srcset.split(","):
            part = part.strip()
            pieces = part.split()
            if len(pieces) >= 2:
                candidate_url = pieces[0]
                width_str = pieces[1].rstrip("w")
                try:
                    w = int(width_str)
                    if w > best_width and not _should_filter_image(candidate_url):
                        best_width = w
                        best_url = candidate_url
                except ValueError:
                    pass
        if best_url:
            return best_url

    # src = direct source (skip SVG placeholders)
    url = img_tag.get("src")
    if url and not url.startswith("data:") and not _should_filter_image(url):
        return url

    return None


def _extract_images(content_div: Tag) -> list[dict]:
    """
    Extract content images from ALiEM posts.
    PV Cards often have a main card image. Clinical posts have inline figures.
    """
    images = []
    current_section = "Introduction"
    seen_urls = set()

    for child in content_div.children:
        if not isinstance(child, Tag):
            continue

        # Check for content-end marker
        el_text = child.get_text(strip=True)
        should_stop = False
        for marker in CONTENT_END_MARKERS:
            if el_text.startswith(marker):
                should_stop = True
                break
        if should_stop:
            break

        # Track section headings
        if child.name in ("h2", "h3", "h4", "h5", "h6"):
            heading_text = child.get_text(strip=True)
            heading_text = re.sub(r"\s+", " ", heading_text).strip()
            if heading_text:
                current_section = heading_text
            continue

        # Find ALL img tags inside this child element
        img_tags = []
        if child.name == "img":
            img_tags.append(child)
        else:
            img_tags.extend(child.find_all("img"))

        for img in img_tags:
            url = _get_image_url(img)
            if not url:
                continue

            # Deduplicate
            base_url = url.split("?")[0]
            if base_url in seen_urls:
                continue
            seen_urls.add(base_url)

            # Skip tiny icons
            width = img.get("width")
            if width:
                try:
                    if int(width) < 50:
                        continue
                except (ValueError, TypeError):
                    pass

            alt = img.get("alt", "")
            title = img.get("data-image-title", "") or img.get("title", "")
            title = unescape(title) if title else ""

            caption = ""
            parent_figure = img.find_parent("figure")
            if parent_figure:
                figcaption = parent_figure.find("figcaption")
                if figcaption:
                    caption = figcaption.get_text(separator=" ", strip=True)

            filename = url.split("/")[-1].split("?")[0] if "/" in url else ""
            label = title or alt or caption or filename.rsplit(".", 1)[0].replace("-", " ")

            images.append({
                "url": url,
                "alt": alt,
                "title": title,
                "caption": caption,
                "label": label,
                "section": current_section,
                "filename": filename,
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
            # Bucket uses uniform access with allUsers objectViewer

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


def _upload_metadata_to_gcs(slug: str, title: str, images: list[dict], track_a_type: str):
    """Upload image metadata JSON to GCS for API image lookup."""
    try:
        client = gcs.Client()
        bucket = client.bucket(GCS_BUCKET_NAME)

        safe_slug = _safe_filename(slug)
        metadata = {
            "protocol_id": slug,
            "title": title,
            "source": "aliem",
            "content_type": track_a_type,
            "license": "CC BY-NC-ND 3.0",
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
    Fetch and extract structured content from a single ALiEM page.
    Returns a dict with title, sections, images, metadata, etc.
    """
    url = f"{BASE_URL}/{slug}/"
    log.info(f"Scraping: {url}")

    resp = fetch(url)
    if not resp:
        return None

    if resp.status_code == 404:
        log.warning(f"  404: {url}")
        return None

    html = resp.text
    soup = BeautifulSoup(html, "lxml")

    # Detect soft 404
    title_check = soup.find("title")
    if title_check and "page not found" in title_check.get_text().lower():
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
    author = yoast_meta["author"] or html_meta["author"] or "ALiEM"
    categories = html_meta["categories"] or yoast_meta["article_sections"]
    tags = html_meta["tags"]
    date_published = yoast_meta["date_published"] or html_meta["date"]
    date_modified = yoast_meta["date_modified"]
    track_a_type = _get_track_a_type(slug)

    # --- Content div ---
    content_div = _get_content_div(soup)
    if not content_div:
        log.warning(f"  No content div found for {slug}")
        return None

    # --- Strip noise ---
    _strip_noise(content_div)

    # --- Extract images ---
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

    # Determine license text based on content type
    if track_a_type == "pv_card":
        license_note = "Paucis Verbis Card — CC BY-NC-ND 3.0"
    elif track_a_type == "medic":
        license_note = "MEdIC Series — CC BY-NC-ND 3.0"
    else:
        license_note = "CC BY-NC-ND 3.0"

    result = {
        "slug": slug,
        "url": url,
        "title": title,
        "author": author,
        "date_published": date_published,
        "date_modified": date_modified,
        "last_scraped": _now_iso(),
        "content_hash": _content_hash(full_text),
        "description": yoast_meta["description"],
        "categories": categories,
        "tags": tags,
        "article_sections": yoast_meta["article_sections"],
        "word_count": yoast_meta["word_count"],
        "content_type": track_a_type,
        "license": "CC BY-NC-ND 3.0",
        "attribution": f"Content from ALiEM (aliem.com) — {url} — by {author}. Licensed under CC BY-NC-ND 3.0.",
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
        f"**Source:** [ALiEM]({url}) | **Author:** {author}",
        f"**Date:** {date_published or date_modified or 'N/A'} | **Category:** {', '.join(categories) if categories else 'N/A'}",
        f"**License:** {license_note}",
        "",
    ]
    for section in sections:
        prefix = "#" * min(section["level"], 6)
        md_lines.append(f"{prefix} {section['heading']}")
        md_lines.append("")
        md_lines.append(section["content"])
        md_lines.append("")
    md_lines.append("---")
    md_lines.append(f"*Content from [ALiEM]({url}) by {author}. Licensed under CC BY-NC-ND 3.0.*")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    # --- Upload metadata to GCS ---
    if upload_gcs:
        _upload_metadata_to_gcs(slug, title, images, track_a_type)

    log.info(
        f"  ✅ {title}: {len(sections)} sections, "
        f"{len(images)} images, {len(categories)} categories"
    )
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ALiEM Scraper (Track A: PV Cards + MEdIC)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--test", action="store_true", help="Test with sample PV Card and MEdIC pages")
    group.add_argument("--topic", type=str, help="Scrape a specific topic slug")
    group.add_argument("--url", type=str, help="Scrape a specific full URL")
    group.add_argument("--multi", nargs="+", help="Scrape multiple slugs")
    parser.add_argument("--no-gcs", action="store_true", help="Skip GCS upload (local only)")

    args = parser.parse_args()
    upload_gcs = not args.no_gcs

    if args.test:
        # Test with representative Track A pages
        test_slugs = [
            "paucis-verbis-hyperkalemia-management",       # PV Card
            "paucis-verbis-red-eye",                        # PV Card
            "medic-series-case-lazy-learners",              # MEdIC Series
        ]
        for slug in test_slugs:
            print(f"\n{'='*70}")
            print(f"Testing: {slug}")
            print(f"{'='*70}")
            result = extract_page(slug, upload_gcs=upload_gcs)
            if result:
                print(f"  Title:        {result['title']}")
                print(f"  Author:       {result['author']}")
                print(f"  Content type: {result['content_type']}")
                print(f"  Categories:   {result['categories']}")
                print(f"  Sections:     {len(result['sections'])}")
                for s in result["sections"]:
                    preview = s["content"][:60].replace("\n", " ")
                    print(f"    [{s['order']}] {s['heading']}: {preview}...")
                print(f"  Images:       {len(result['images'])}")
                for img in result["images"]:
                    print(f"    📸 [{img['section']}] {img['label']}")
                print(f"  License:      {result['license']}")
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
