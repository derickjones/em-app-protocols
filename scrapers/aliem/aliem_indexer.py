#!/usr/bin/env python3
"""
ALiEM RAG Indexer
Creates a separate Vertex AI RAG corpus for ALiEM content (Track A: PV Cards + MEdIC Series)
and indexes scraped markdown files into it.

Usage:
    # Create the ALiEM corpus (one-time)
    python aliem_indexer.py --create-corpus

    # Index a single file
    python aliem_indexer.py --index-file output/processed/aliem-pv-card-hyperkalemia.md

    # Index all processed markdown files
    python aliem_indexer.py --index-all

    # Check corpus status
    python aliem_indexer.py --status

    # List indexed files
    python aliem_indexer.py --list-files

    # Validate all files are indexed
    python aliem_indexer.py --validate
"""

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import google.auth
import google.auth.transport.requests
import requests as http_requests
from google.cloud import storage as gcs

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_ID = os.environ.get("PROJECT_ID", "clinical-assistant-457902")
PROJECT_NUMBER = os.environ.get("PROJECT_NUMBER", "930035889332")
RAG_LOCATION = os.environ.get("RAG_LOCATION", "us-west4")

GCS_BUCKET_NAME = f"{PROJECT_ID}-aliem"

CORPUS_DISPLAY_NAME = "aliem-track-a"
CORPUS_DESCRIPTION = (
    "ALiEM Track A content (CC BY-NC-ND 3.0) — PV Cards (visual learning cards "
    "for core EM topics) and MEdIC Series (medical education cases and discussions) "
    "from ALiEM (aliem.com)"
)

# Paths
OUTPUT_DIR = Path(__file__).parent / "output"
PROCESSED_DIR = OUTPUT_DIR / "processed"
METADATA_DIR = OUTPUT_DIR / "metadata"
CONFIG_PATH = Path(__file__).parent / "aliem_rag_config.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("aliem-indexer")

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def get_access_token() -> str:
    """Get OAuth2 access token for Vertex AI API calls."""
    credentials, _ = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token


def api_headers() -> dict:
    return {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Corpus management
# ---------------------------------------------------------------------------

BASE_URL = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1"
PARENT = f"projects/{PROJECT_ID}/locations/{RAG_LOCATION}"


def create_corpus() -> dict:
    """Create a new RAG corpus for ALiEM content."""
    url = f"{BASE_URL}/{PARENT}/ragCorpora"

    payload = {
        "display_name": CORPUS_DISPLAY_NAME,
        "description": CORPUS_DESCRIPTION,
        "rag_embedding_model_config": {
            "vertex_prediction_endpoint": {
                "endpoint": f"projects/{PROJECT_ID}/locations/{RAG_LOCATION}/publishers/google/models/text-embedding-005"
            }
        },
    }

    log.info(f"Creating corpus '{CORPUS_DISPLAY_NAME}'...")
    resp = http_requests.post(url, headers=api_headers(), json=payload)

    if resp.status_code not in (200, 201):
        log.error(f"Failed to create corpus: {resp.status_code} - {resp.text}")
        return {}

    result = resp.json()
    log.info(f"Corpus creation started: {result.get('name', 'unknown')}")

    # The response is a long-running operation — poll until done
    op_name = result.get("name", "")
    if op_name:
        corpus_info = _poll_operation(op_name)
        if corpus_info:
            _save_config(corpus_info)
            return corpus_info

    return result


def _poll_operation(op_name: str, max_wait: int = 120) -> dict | None:
    """Poll a long-running operation until it completes."""
    url = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/{op_name}"
    start = time.time()

    while time.time() - start < max_wait:
        resp = http_requests.get(url, headers=api_headers())
        if resp.status_code != 200:
            log.error(f"Poll failed: {resp.status_code}")
            return None

        data = resp.json()
        if data.get("done"):
            if "error" in data:
                log.error(f"Operation failed: {data['error']}")
                return None
            log.info("Operation completed successfully")
            return data.get("response", data)

        log.info("  Waiting for operation to complete...")
        time.sleep(5)

    log.error("Operation timed out")
    return None


def _save_config(corpus_info: dict):
    """Save corpus config for later use."""
    corpus_name = corpus_info.get("name", "")
    corpus_id = corpus_name.split("/")[-1] if corpus_name else ""

    config = {
        "project_id": PROJECT_ID,
        "project_number": PROJECT_NUMBER,
        "location": RAG_LOCATION,
        "corpus_id": corpus_id,
        "corpus_name": corpus_name,
        "corpus_display_name": CORPUS_DISPLAY_NAME,
        "embedding_model": "text-embedding-005",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    log.info(f"Config saved to {CONFIG_PATH}")


def load_config() -> dict:
    """Load saved corpus config."""
    if not CONFIG_PATH.exists():
        log.error(f"No config found at {CONFIG_PATH}. Run --create-corpus first.")
        return {}
    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_corpus_status() -> dict:
    """Get the status of the ALiEM corpus."""
    config = load_config()
    if not config:
        return {}

    corpus_name = config["corpus_name"]
    url = f"{BASE_URL}/{corpus_name}"

    resp = http_requests.get(url, headers=api_headers())
    if resp.status_code != 200:
        log.error(f"Failed to get corpus status: {resp.status_code} - {resp.text}")
        return {}

    return resp.json()


def list_rag_files() -> list:
    """List all files indexed in the ALiEM corpus."""
    config = load_config()
    if not config:
        return []

    corpus_name = config["corpus_name"]
    url = f"{BASE_URL}/{corpus_name}/ragFiles"

    all_files = []
    page_token = None

    while True:
        params = {}
        if page_token:
            params["pageToken"] = page_token

        resp = http_requests.get(url, headers=api_headers(), params=params)
        if resp.status_code != 200:
            log.error(f"Failed to list files: {resp.status_code} - {resp.text}")
            return all_files

        data = resp.json()
        all_files.extend(data.get("ragFiles", []))

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return all_files


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------


def index_file(md_path: Path) -> bool:
    """
    Index a single markdown file into the ALiEM RAG corpus.
    Uploads to GCS then imports into RAG corpus.
    Also uploads metadata JSON with image references.
    """
    config = load_config()
    if not config:
        return False

    corpus_name = config["corpus_name"]

    if not md_path.exists():
        log.error(f"File not found: {md_path}")
        return False

    content = md_path.read_text(encoding="utf-8")
    slug = md_path.stem

    log.info(f"Indexing {slug} ({len(content)} chars)...")
    success = _index_via_import(corpus_name, md_path, slug, content)

    # Also upload metadata if the processed JSON exists
    if success:
        _upload_metadata_for_slug(slug)

    return success


def _upload_metadata_for_slug(slug: str):
    """Upload image metadata to GCS from the processed JSON file."""
    json_path = PROCESSED_DIR / f"{slug}.json"
    if not json_path.exists():
        log.info(f"  No processed JSON for {slug}, skipping metadata upload")
        return

    try:
        with open(json_path) as f:
            data = json.load(f)

        images = data.get("images", [])

        metadata = {
            "slug": slug,
            "title": data.get("title", slug),
            "url": data.get("url", f"https://www.aliem.com/{slug}/"),
            "author": data.get("author", "Unknown"),
            "categories": data.get("categories", []),
            "tags": data.get("tags", []),
            "content_type": data.get("content_type", "unknown"),
            "date_published": data.get("date_published"),
            "date_modified": data.get("date_modified"),
            "images": [
                {
                    "url": img.get("url", ""),
                    "alt": img.get("alt", ""),
                    "caption": img.get("caption", ""),
                    "gcs_path": img.get("gcs_path", ""),
                }
                for img in images
                if img.get("url")
            ],
            "license": "CC BY-NC-ND 3.0",
            "source": "ALiEM",
        }

        client = gcs.Client(project=PROJECT_ID)
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(f"metadata/{slug}.json")
        blob.upload_from_string(
            json.dumps(metadata, indent=2),
            content_type="application/json",
        )
        log.info(f"  📋 Metadata uploaded: metadata/{slug}.json ({len(images)} images)")
    except Exception as e:
        log.warning(f"  ⚠️ Failed to upload metadata for {slug}: {e}")


def _index_via_import(corpus_name: str, md_path: Path, slug: str, content: str) -> bool:
    """Upload to GCS first, then import into RAG corpus."""
    gcs_path = f"processed/{slug}.md"

    client = gcs.Client(project=PROJECT_ID)
    try:
        bucket = client.get_bucket(GCS_BUCKET_NAME)
    except Exception:
        log.info(f"Creating GCS bucket: {GCS_BUCKET_NAME}")
        bucket = client.create_bucket(GCS_BUCKET_NAME, location="us-west4")

    # Upload markdown to GCS
    blob = bucket.blob(gcs_path)
    blob.upload_from_string(content, content_type="text/markdown")
    gcs_uri = f"gs://{GCS_BUCKET_NAME}/{gcs_path}"

    # Import into RAG corpus with retry logic for rate limits
    url = f"{BASE_URL}/{corpus_name}/ragFiles:import"

    payload = {
        "importRagFilesConfig": {
            "gcsSource": {
                "uris": [gcs_uri]
            },
            "ragFileChunkingConfig": {
                "chunkSize": 1024,
                "chunkOverlap": 200,
            },
        }
    }

    max_retries = 5
    for attempt in range(max_retries):
        resp = http_requests.post(url, headers=api_headers(), json=payload)

        if resp.status_code in (200, 201):
            result = resp.json()
            op_name = result.get("name", "")
            if op_name:
                log.info(f"  📤 Import started: {slug}")
                return True
            log.info(f"  ✅ Indexed: {slug}")
            return True
        elif resp.status_code == 429:
            wait_time = (2 ** attempt) * 2
            log.warning(f"  ⏳ Rate limit hit for {slug}, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
            time.sleep(wait_time)
        elif resp.status_code == 400 and "FAILED_PRECONDITION" in resp.text:
            wait_time = (2 ** attempt) * 3
            log.warning(f"  ⏳ Corpus busy for {slug}, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
            time.sleep(wait_time)
        else:
            log.error(f"Import failed: {resp.status_code} - {resp.text}")
            return False

    log.error(f"  ❌ Failed to index {slug} after {max_retries} attempts (rate limit)")
    return False


def index_all():
    """Index all processed markdown files sequentially."""
    md_files = sorted(PROCESSED_DIR.glob("*.md"))
    if not md_files:
        log.error(f"No markdown files found in {PROCESSED_DIR}")
        return

    log.info(f"Found {len(md_files)} markdown files to index")

    # Check which files are already in the corpus to enable resume
    log.info("Checking corpus for already-indexed files...")
    try:
        indexed_files = list_rag_files()
        already_indexed = {f.get("displayName", "").replace(".md", "") for f in indexed_files}
        log.info(f"Already indexed in corpus: {len(already_indexed)} files")
    except Exception as e:
        log.warning(f"Could not list corpus files, will re-index all: {e}")
        already_indexed = set()

    to_index = [md for md in md_files if md.stem not in already_indexed]
    log.info(f"Skipping {len(md_files) - len(to_index)} already-indexed files")
    log.info(f"Remaining to index: {len(to_index)} files")

    if not to_index:
        log.info("✅ All files already indexed!")
        return

    success = 0
    failed = 0
    skipped = len(md_files) - len(to_index)
    start_time = time.time()

    for i, md in enumerate(to_index, 1):
        slug = md.stem
        try:
            ok = index_file(md)
            if ok:
                success += 1
            else:
                failed += 1
        except Exception as e:
            log.error(f"Error indexing {slug}: {e}")
            failed += 1

        # Wait between imports to let the previous operation complete
        time.sleep(2.0)

        if i % 25 == 0:
            elapsed = time.time() - start_time
            rate = i / elapsed
            remaining = len(to_index) - i
            eta = remaining / rate if rate > 0 else 0
            log.info(f"Progress: {i}/{len(to_index)} ({success} success, {failed} failed, {skipped} skipped) - ETA: {eta/60:.1f}min")

    elapsed = time.time() - start_time
    log.info(f"\n{'='*60}")
    log.info(f"Indexing complete in {elapsed/60:.1f} minutes")
    log.info(f"Success: {success}, Failed: {failed}, Skipped (already indexed): {skipped}")
    log.info(f"{'='*60}")

    _update_config_stats(success + skipped, failed)


def _update_config_stats(success: int, failed: int):
    """Update config file with indexing statistics."""
    config = load_config()
    if not config:
        return

    config["last_indexed"] = datetime.now(timezone.utc).isoformat()
    config["total_files_indexed"] = success
    config["indexing_failures"] = failed

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def validate_indexing():
    """Validate that all local markdown files are indexed in the corpus."""
    log.info("Validating indexing...")

    local_files = {md.stem for md in PROCESSED_DIR.glob("*.md")}
    log.info(f"Local markdown files: {len(local_files)}")

    indexed_files = list_rag_files()
    indexed_slugs = {f.get("displayName", "").replace(".md", "") for f in indexed_files}
    log.info(f"Indexed files in corpus: {len(indexed_slugs)}")

    missing = local_files - indexed_slugs
    if missing:
        log.warning(f"\n⚠️ Missing {len(missing)} files from corpus:")
        for slug in sorted(missing)[:20]:
            log.warning(f"  - {slug}")
        if len(missing) > 20:
            log.warning(f"  ... and {len(missing) - 20} more")
    else:
        log.info("✅ All local files are indexed!")

    extra = indexed_slugs - local_files
    if extra:
        log.warning(f"\n⚠️ Found {len(extra)} extra files in corpus (not in local):")
        for slug in sorted(extra)[:10]:
            log.warning(f"  - {slug}")

    return len(missing) == 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="ALiEM RAG Indexer")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--create-corpus", action="store_true", help="Create the ALiEM RAG corpus")
    group.add_argument("--index-file", type=str, help="Index a single markdown file")
    group.add_argument("--index-all", action="store_true", help="Index all processed markdown files")
    group.add_argument("--status", action="store_true", help="Check corpus status")
    group.add_argument("--list-files", action="store_true", help="List indexed files")
    group.add_argument("--validate", action="store_true", help="Validate all files are indexed")

    args = parser.parse_args()

    if args.create_corpus:
        result = create_corpus()
        if result:
            print(f"\n✅ Corpus created!")
            print(json.dumps(result, indent=2))
            print(f"\n💡 Next step: python aliem_indexer.py --index-all")
        else:
            print("❌ Failed to create corpus")

    elif args.index_file:
        md_path = Path(args.index_file)
        if index_file(md_path):
            print(f"✅ Indexed {md_path.stem}")
        else:
            print(f"❌ Failed to index {md_path.stem}")

    elif args.index_all:
        index_all()

    elif args.status:
        status = get_corpus_status()
        if status:
            print(json.dumps(status, indent=2))
        else:
            print("❌ Could not get corpus status")

        config = load_config()
        if config:
            print(f"\n📊 Config Summary:")
            print(f"  Corpus ID: {config.get('corpus_id', 'N/A')}")
            print(f"  Display Name: {config.get('corpus_display_name', 'N/A')}")
            print(f"  Last Indexed: {config.get('last_indexed', 'Never')}")
            print(f"  Files Indexed: {config.get('total_files_indexed', 0)}")
            print(f"  Failures: {config.get('indexing_failures', 0)}")

    elif args.list_files:
        files = list_rag_files()
        if files:
            print(f"Found {len(files)} indexed files:")
            for i, f in enumerate(files[:20], 1):
                print(f"  {i}. {f.get('displayName', 'unknown')}")
            if len(files) > 20:
                print(f"  ... and {len(files) - 20} more")
        else:
            print("No files indexed yet")

    elif args.validate:
        validate_indexing()


if __name__ == "__main__":
    main()
