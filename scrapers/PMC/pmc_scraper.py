#!/usr/bin/env python3
"""
PMC Article Scraper
Core per-article scraping logic using NCBI BioC API.
Tries full-text first, falls back to abstract-only.
Extracts images from PMC HTML for full-text articles.

Used by pmc_bulk_scrape.py — not typically run directly.
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from google.cloud import storage as gcs

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_ID = os.environ.get("PROJECT_ID", "clinical-assistant-457902")
GCS_BUCKET_NAME = f"{PROJECT_ID}-pmc"

BIOC_PMC_URL = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json/{pmcid}/unicode"
BIOC_PUBMED_URL = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pubmed.cgi/BioC_json/{pmid}/unicode"
PMC_HTML_URL = "https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"

# Paths
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output"
RAW_DIR = OUTPUT_DIR / "raw"
PROCESSED_DIR = OUTPUT_DIR / "processed"

for d in [RAW_DIR, PROCESSED_DIR]:
    d.mkdir(parents=True, exist_ok=True)

log = logging.getLogger("pmc-scraper")

# Reusable HTTP session
_session = requests.Session()
_session.headers.update({"User-Agent": "EMProtocolBot/1.0 (research; derickdavidjones@gmail.com)"})

# GCS client (lazy init)
_gcs_client: Optional[gcs.Client] = None
_gcs_bucket = None


def _get_gcs_bucket():
    """Lazy-init GCS bucket (thread-safe)."""
    global _gcs_client, _gcs_bucket
    if _gcs_bucket is None:
        _gcs_client = gcs.Client(project=PROJECT_ID)
        try:
            _gcs_bucket = _gcs_client.get_bucket(GCS_BUCKET_NAME)
        except Exception:
            try:
                log.info(f"Creating GCS bucket: {GCS_BUCKET_NAME}")
                _gcs_bucket = _gcs_client.create_bucket(GCS_BUCKET_NAME, location="us-west4")
            except Exception:
                # Another thread may have created it — retry get
                _gcs_bucket = _gcs_client.get_bucket(GCS_BUCKET_NAME)
    return _gcs_bucket


# ---------------------------------------------------------------------------
# BioC Full-Text Parsing
# ---------------------------------------------------------------------------


def _fetch_bioc_fulltext(pmcid: str) -> Optional[dict]:
    """
    Fetch full-text article from BioC PMC API.
    Returns parsed article dict or None if not available.
    """
    url = BIOC_PMC_URL.format(pmcid=pmcid)
    resp = _session.get(url, timeout=30)

    if resp.status_code != 200:
        return None

    # Check if it's actually JSON (full text available)
    content_type = resp.headers.get("Content-Type", "")
    if "application/json" not in content_type and "text/json" not in content_type:
        # Not full text — try to detect JSON anyway
        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError):
            return None
    else:
        data = resp.json()

    if not data or not isinstance(data, list) or len(data) == 0:
        return None

    # Save raw response
    raw_path = RAW_DIR / f"{pmcid}_fulltext.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    return _parse_bioc_article(data, section_label="section_type", article_type="full_text")


def _fetch_bioc_abstract(pmcid: str) -> Optional[dict]:
    """
    Fetch abstract-only from BioC PubMed API.
    Requires converting PMCID to PMID first.
    """
    # Strip "PMC" prefix to get numeric ID for PubMed lookup
    pmid = pmcid.replace("PMC", "")

    url = BIOC_PUBMED_URL.format(pmid=pmid)
    resp = _session.get(url, timeout=30)

    if resp.status_code != 200:
        return None

    try:
        data = resp.json()
    except (json.JSONDecodeError, ValueError):
        return None

    if not data or not isinstance(data, list) or len(data) == 0:
        return None

    # Save raw response
    raw_path = RAW_DIR / f"{pmcid}_abstract.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    article = _parse_bioc_article(data, section_label="type", article_type="abstract")

    if article:
        # Abstract-only articles link to PubMed, not PMC
        article["url"] = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

    return article


def _parse_bioc_article(data: list, section_label: str, article_type: str) -> Optional[dict]:
    """
    Parse a BioC JSON response into a structured article dict.
    """
    try:
        doc = data[0]["documents"][0]
        passages = doc.get("passages", [])
    except (IndexError, KeyError):
        return None

    if not passages:
        return None

    # Sort passages by offset
    passages_sorted = sorted(passages, key=lambda p: p.get("offset", 0))

    title = ""
    authors = ""
    sections = []
    current_section = None

    for p in passages_sorted:
        infons = p.get("infons", {})
        section_type = infons.get(section_label, "").strip().lower()
        text = p.get("text", "").strip()

        if not text:
            continue

        # Extract title
        if section_type == "title" and not title:
            title = text
            continue

        # Extract authors from front matter
        if section_type in ("front", "title_1") and "author" in text.lower():
            authors = text
            continue

        # Map section types to readable names
        section_name = _normalize_section_name(section_type, infons)

        if section_name and section_name != (current_section or {}).get("name"):
            current_section = {"name": section_name, "text": text}
            sections.append(current_section)
        elif current_section:
            current_section["text"] += "\n" + text
        else:
            current_section = {"name": "Content", "text": text}
            sections.append(current_section)

    if not title and sections:
        title = sections[0]["text"][:200]

    return {
        "title": title,
        "authors": _clean_authors(authors),
        "type": article_type,
        "sections": sections,
    }


def _normalize_section_name(section_type: str, infons: dict) -> str:
    """Map BioC section types to readable section names."""
    # Try the section title from infons first
    section_title = infons.get("section_title_1", "") or infons.get("section_title", "")
    if section_title:
        return section_title.strip()

    mapping = {
        "abstract": "Abstract",
        "intro": "Introduction",
        "introduction": "Introduction",
        "methods": "Methods",
        "materials": "Methods",
        "results": "Results",
        "discuss": "Discussion",
        "discussion": "Discussion",
        "conclusion": "Conclusions",
        "conclusions": "Conclusions",
        "ref": None,  # Skip references
        "references": None,
        "table": "Tables",
        "fig": "Figures",
        "figure": "Figures",
        "supplement": "Supplementary Material",
        "ack": "Acknowledgments",
        "acknowledgment": "Acknowledgments",
        "competing": "Conflicts of Interest",
        "conflict": "Conflicts of Interest",
        "funding": "Funding",
        "background": "Background",
        "case": "Case Report",
    }

    for key, value in mapping.items():
        if key in section_type:
            return value

    return section_type.replace("_", " ").title() if section_type else "Content"


def _clean_authors(raw: str) -> str:
    """Clean author string, truncate with et al. if long."""
    if not raw or len(raw) < 3:
        return ""

    # Remove common prefixes
    raw = re.sub(r"^(Authors?:?\s*)", "", raw, flags=re.IGNORECASE).strip()

    # If it's very long, try to extract just names
    if len(raw) > 200:
        # Take first 3 author-like names and add et al.
        parts = re.split(r"[,;]\s*", raw)
        if len(parts) > 3:
            return ", ".join(parts[:3]) + ", et al."

    return raw


# ---------------------------------------------------------------------------
# Image Extraction (full-text articles only)
# ---------------------------------------------------------------------------


def _extract_images(pmcid: str) -> list[dict]:
    """
    Fetch the PMC HTML page and extract figure images.
    Downloads to GCS and returns metadata list.
    """
    url = PMC_HTML_URL.format(pmcid=pmcid)

    try:
        resp = _session.get(url, timeout=30)
        if resp.status_code != 200:
            return []
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    images = []
    bucket = _get_gcs_bucket()

    # Find figure images — PMC uses various patterns
    figure_imgs = []

    # Pattern 1: <figure> tags with <img>
    for fig in soup.find_all("figure"):
        img = fig.find("img")
        if img and img.get("src"):
            caption = ""
            cap_el = fig.find("figcaption") or fig.find(class_=re.compile(r"caption|fig-caption"))
            if cap_el:
                caption = cap_el.get_text(strip=True)[:300]
            figure_imgs.append({"src": img["src"], "alt": img.get("alt", caption), "caption": caption})

    # Pattern 2: Images with class containing "fig" or inside figure-like divs
    for img in soup.find_all("img", src=True):
        src = img["src"]
        # Skip tiny icons, logos, tracking pixels
        if any(skip in src.lower() for skip in [
            "icon", "logo", "tracking", "pixel", "badge", "button",
            "spinner", "arrow", "caret", "/i/", "1x1", "spacer",
            "pubmed-logo", "pmc-logo", "ncbi-logo", "nih-logo",
        ]):
            continue

        # Check dimensions if available
        width = img.get("width", "")
        height = img.get("height", "")
        try:
            if width and int(width) < 50:
                continue
            if height and int(height) < 50:
                continue
        except ValueError:
            pass

        # Check if this image is already captured via <figure>
        already_found = any(f["src"] == src for f in figure_imgs)
        if not already_found:
            alt = img.get("alt", "")
            # Only include if it looks like a figure
            parent = img.find_parent(["figure", "div", "table"])
            if parent and ("fig" in str(parent.get("class", "")).lower() or
                          "fig" in str(parent.get("id", "")).lower()):
                figure_imgs.append({"src": src, "alt": alt, "caption": alt})

    # Download and upload to GCS
    for i, fig in enumerate(figure_imgs):
        src = fig["src"]

        # Resolve relative URLs
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = urljoin("https://pmc.ncbi.nlm.nih.gov", src)
        elif not src.startswith("http"):
            src = urljoin(url, src)

        try:
            img_resp = _session.get(src, timeout=15)
            if img_resp.status_code != 200:
                continue

            # Determine filename
            ext = _guess_extension(src, img_resp.headers.get("Content-Type", ""))
            filename = f"figure_{i+1}{ext}"

            # Upload to GCS
            gcs_path = f"images/{pmcid}/{filename}"
            blob = bucket.blob(gcs_path)
            blob.upload_from_string(
                img_resp.content,
                content_type=img_resp.headers.get("Content-Type", "image/png"),
            )
            blob.make_public()

            gcs_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{gcs_path}"

            images.append({
                "url": gcs_url,
                "alt": fig.get("alt", f"Figure {i+1}"),
                "caption": fig.get("caption", ""),
                "page": i,
            })

            log.debug(f"  📸 {filename} → {gcs_path}")

        except Exception as e:
            log.debug(f"  ⚠️ Failed to download image: {e}")
            continue

    return images


def _guess_extension(url: str, content_type: str) -> str:
    """Guess file extension from URL or content type."""
    # Try URL first
    for ext in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".tiff"]:
        if ext in url.lower():
            return ext

    # Try content type
    ct_map = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/svg+xml": ".svg",
        "image/webp": ".webp",
    }
    return ct_map.get(content_type.split(";")[0].strip(), ".png")


# ---------------------------------------------------------------------------
# Metadata Upload
# ---------------------------------------------------------------------------


def _upload_metadata_to_gcs(pmcid: str, article: dict, images: list):
    """Upload article metadata + image info to GCS for API lookups."""
    metadata = {
        "protocol_id": pmcid,
        "title": article.get("title", ""),
        "journal": article.get("journal", ""),
        "authors": article.get("authors", ""),
        "year": article.get("year", ""),
        "url": article.get("url", ""),
        "type": article.get("type", ""),
        "images": [
            {"url": img["url"], "alt": img.get("alt", ""), "caption": img.get("caption", ""), "page": img.get("page", i)}
            for i, img in enumerate(images)
        ],
    }

    try:
        bucket = _get_gcs_bucket()
        blob = bucket.blob(f"metadata/{pmcid}.json")
        blob.upload_from_string(
            json.dumps(metadata, indent=2),
            content_type="application/json",
        )
        log.debug(f"  📋 Metadata uploaded: metadata/{pmcid}.json")
    except Exception as e:
        log.warning(f"  ⚠️ Failed to upload metadata for {pmcid}: {e}")


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------


def extract_article(pmcid: str, journal: str = "", images_enabled: bool = True) -> Optional[dict]:
    """
    Scrape a single PMC article. Tries full-text, falls back to abstract.
    Downloads images for full-text articles and uploads metadata to GCS.
    Saves processed .md and .json files locally.

    Returns article dict with summary info, or None on failure.
    """
    # Try full text first
    article = _fetch_bioc_fulltext(pmcid)
    if article:
        article["type"] = "full_text"
    else:
        # Fall back to abstract
        article = _fetch_bioc_abstract(pmcid)
        if article:
            article["type"] = "abstract"

    if not article:
        return None

    # Add metadata
    article["pmcid"] = pmcid
    article["journal"] = journal
    article["url"] = article.get("url", f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/")

    # Try to extract year from sections or default to empty
    article["year"] = _extract_year(article)

    # Extract images (full-text only)
    # Fetches PMC HTML page, finds <figure> images, uploads to GCS
    images = []
    if images_enabled and article["type"] == "full_text":
        images = _extract_images(pmcid)
        article["images"] = images

    # Upload metadata to GCS (article info + image URLs for API lookups)
    if images_enabled:
        _upload_metadata_to_gcs(pmcid, article, images)

    # Save processed markdown
    md_content = _build_markdown(article)
    md_path = PROCESSED_DIR / f"{pmcid}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # Save processed JSON
    json_path = PROCESSED_DIR / f"{pmcid}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(article, f, indent=2, ensure_ascii=False)

    return {
        "pmcid": pmcid,
        "title": article["title"],
        "journal": journal,
        "type": article["type"],
        "sections": len(article.get("sections", [])),
        "images": len(images),
    }


def _extract_year(article: dict) -> str:
    """Try to extract publication year from article content."""
    # Check if there's a date-like pattern in early sections
    for section in article.get("sections", [])[:3]:
        text = section.get("text", "")
        match = re.search(r"(20[12]\d)", text)
        if match:
            return match.group(1)
    return ""


def _build_markdown(article: dict) -> str:
    """Build a markdown document from the article data."""
    lines = []

    lines.append(f"# {article.get('title', 'Untitled')}")
    lines.append("")

    if article.get("journal"):
        lines.append(f"**Journal:** {article['journal']}")
    if article.get("authors"):
        lines.append(f"**Authors:** {article['authors']}")
    if article.get("year"):
        lines.append(f"**Year:** {article['year']}")
    lines.append(f"**PMCID:** {article.get('pmcid', '')}")
    lines.append(f"**URL:** {article.get('url', '')}")
    lines.append(f"**Type:** {article.get('type', '')}")
    lines.append("")

    for section in article.get("sections", []):
        name = section.get("name", "")
        text = section.get("text", "")

        if name:
            lines.append(f"## {name}")
            lines.append("")

        if text:
            lines.append(text)
            lines.append("")

    return "\n".join(lines)
