#!/usr/bin/env python3
"""
LITFL RAG Indexer
Creates a separate Vertex AI RAG corpus for LITFL content
and indexes scraped markdown files into it.

Usage:
    # Create the LITFL corpus (one-time)
    python litfl_indexer.py --create-corpus

    # Index a single file
    python litfl_indexer.py --index-file output/processed/etomidate.md

    # Index all processed markdown files
    python litfl_indexer.py --index-all

    # Index all with parallel workers
    python litfl_indexer.py --index-all --workers 10

    # Check corpus status
    python litfl_indexer.py --status

    # List indexed files
    python litfl_indexer.py --list-files

    # Validate all files are indexed
    python litfl_indexer.py --validate
"""

import argparse
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
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

CORPUS_DISPLAY_NAME = "litfl-foamed"
CORPUS_DESCRIPTION = (
    "FOAMed clinical education content from Life in the Fast Lane (litfl.com) - "
    "pharmacology, ECG interpretation, critical care, toxicology, imaging cases"
)

# Paths
OUTPUT_DIR = Path(__file__).parent / "output"
PROCESSED_DIR = OUTPUT_DIR / "processed"
METADATA_DIR = OUTPUT_DIR / "metadata"
CONFIG_PATH = Path(__file__).parent / "litfl_rag_config.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("litfl-indexer")

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
    """Create a new RAG corpus for LITFL content."""
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
    # Extract corpus name/ID from the response
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
        "created_at": datetime.utcnow().isoformat() + "Z",
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
    """Get the status of the LITFL corpus."""
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
    """List all files indexed in the LITFL corpus."""
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
    Index a single markdown file into the LITFL RAG corpus.
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
    slug = md_path.stem  # e.g. "etomidate"

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
        
        # Create metadata with all relevant info
        metadata = {
            "slug": slug,
            "title": data.get("title", slug),
            "url": data.get("url", f"https://litfl.com/{slug}/"),
            "author": data.get("author", "Unknown"),
            "categories": data.get("categories", []),
            "tags": data.get("tags", []),
            "date_modified": data.get("date_modified"),
            "images": [
                {
                    "gcs_uri": img.get("gcs_uri", ""),
                    "original_url": img.get("original_url", ""),
                    "alt": img.get("alt", ""),
                    "caption": img.get("caption", ""),
                }
                for img in images
                if img.get("gcs_uri")
            ],
            "license": "CC BY-NC-SA 4.0",
            "source": "LITFL",
        }

        client = gcs.Client(project=PROJECT_ID)
        bucket_name = f"{PROJECT_ID}-litfl"
        bucket = client.bucket(bucket_name)
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
    bucket_name = f"{PROJECT_ID}-litfl"
    gcs_path = f"processed/{slug}.md"

    # Ensure bucket exists
    client = gcs.Client(project=PROJECT_ID)
    try:
        bucket = client.get_bucket(bucket_name)
    except Exception:
        log.info(f"Creating GCS bucket: {bucket_name}")
        bucket = client.create_bucket(bucket_name, location="us-west4")

    # Upload to GCS
    blob = bucket.blob(gcs_path)
    blob.upload_from_string(content, content_type="text/markdown")
    gcs_uri = f"gs://{bucket_name}/{gcs_path}"

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

    # Retry with exponential backoff for rate limits and concurrent operation errors
    max_retries = 5
    for attempt in range(max_retries):
        resp = http_requests.post(url, headers=api_headers(), json=payload)

        if resp.status_code in (200, 201):
            result = resp.json()
            op_name = result.get("name", "")
            if op_name:
                # For bulk operations, don't wait for each file
                log.info(f"  📤 Import started: {slug}")
                return True
            log.info(f"  ✅ Indexed: {slug}")
            return True
        elif resp.status_code == 429:
            # Rate limit - wait and retry
            wait_time = (2 ** attempt) * 2  # Exponential backoff: 2, 4, 8, 16, 32 seconds
            log.warning(f"  ⏳ Rate limit hit for {slug}, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
            time.sleep(wait_time)
        elif resp.status_code == 400 and "FAILED_PRECONDITION" in resp.text:
            # Concurrent operation on corpus - wait for it to finish
            wait_time = (2 ** attempt) * 3  # Longer backoff: 3, 6, 12, 24, 48 seconds
            log.warning(f"  ⏳ Corpus busy for {slug}, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
            time.sleep(wait_time)
        else:
            log.error(f"Import failed: {resp.status_code} - {resp.text}")
            return False

    log.error(f"  ❌ Failed to index {slug} after {max_retries} attempts (rate limit)")
    return False


def index_all_worker(md_path: Path) -> tuple[str, bool]:
    """Worker function for parallel indexing."""
    slug = md_path.stem
    try:
        success = index_file(md_path)
        return (slug, success)
    except Exception as e:
        log.error(f"Error indexing {slug}: {e}")
        return (slug, False)


def index_all(workers: int = 5):
    """Index all processed markdown files sequentially to avoid FAILED_PRECONDITION errors."""
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

    # Filter to only files that need indexing
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

    # Sequential processing — corpus only allows one import operation at a time
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
        # and stay under the 60 req/min rate limit
        time.sleep(2.0)

        if i % 50 == 0:
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

    # Update config with indexing stats
    _update_config_stats(success + skipped, failed)


def _update_config_stats(success: int, failed: int):
    """Update config file with indexing statistics."""
    config = load_config()
    if not config:
        return
    
    config["last_indexed"] = datetime.utcnow().isoformat() + "Z"
    config["total_files_indexed"] = success
    config["indexing_failures"] = failed
    
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def validate_indexing():
    """Validate that all local markdown files are indexed in the corpus."""
    log.info("Validating indexing...")
    
    # Get local files
    local_files = {md.stem for md in PROCESSED_DIR.glob("*.md")}
    log.info(f"Local markdown files: {len(local_files)}")
    
    # Get indexed files
    indexed_files = list_rag_files()
    indexed_slugs = {f.get("displayName", "").replace(".md", "") for f in indexed_files}
    log.info(f"Indexed files in corpus: {len(indexed_slugs)}")
    
    # Find missing
    missing = local_files - indexed_slugs
    if missing:
        log.warning(f"\n⚠️ Missing {len(missing)} files from corpus:")
        for slug in sorted(missing)[:20]:  # Show first 20
            log.warning(f"  - {slug}")
        if len(missing) > 20:
            log.warning(f"  ... and {len(missing) - 20} more")
    else:
        log.info("✅ All local files are indexed!")
    
    # Find extra (shouldn't happen)
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
    parser = argparse.ArgumentParser(description="LITFL RAG Indexer")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--create-corpus", action="store_true", help="Create the LITFL RAG corpus")
    group.add_argument("--index-file", type=str, help="Index a single markdown file")
    group.add_argument("--index-all", action="store_true", help="Index all processed markdown files")
    group.add_argument("--status", action="store_true", help="Check corpus status")
    group.add_argument("--list-files", action="store_true", help="List indexed files")
    group.add_argument("--validate", action="store_true", help="Validate all files are indexed")
    
    parser.add_argument("--workers", type=int, default=5, help="Number of parallel workers for --index-all")

    args = parser.parse_args()

    if args.create_corpus:
        result = create_corpus()
        if result:
            print(f"\n✅ Corpus created!")
            print(json.dumps(result, indent=2))
            print(f"\n💡 Next step: python litfl_indexer.py --index-all --workers 10")
        else:
            print("❌ Failed to create corpus")

    elif args.index_file:
        md_path = Path(args.index_file)
        if index_file(md_path):
            print(f"✅ Indexed {md_path.stem}")
        else:
            print(f"❌ Failed to index {md_path.stem}")

    elif args.index_all:
        index_all(workers=args.workers)

    elif args.status:
        status = get_corpus_status()
        if status:
            print(json.dumps(status, indent=2))
        else:
            print("❌ Could not get corpus status")
        
        # Also show config info
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
            for i, f in enumerate(files[:20], 1):  # Show first 20
                print(f"  {i}. {f.get('displayName', 'unknown')}")
            if len(files) > 20:
                print(f"  ... and {len(files) - 20} more")
        else:
            print("No files indexed yet")
    
    elif args.validate:
        validate_indexing()


if __name__ == "__main__":
    main()
