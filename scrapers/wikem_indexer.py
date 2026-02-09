#!/usr/bin/env python3
"""
WikEM RAG Indexer
Creates a separate Vertex AI RAG corpus for WikEM content
and indexes scraped markdown files into it.

Usage:
    # Create the WikEM corpus (one-time)
    python wikem_indexer.py --create-corpus

    # Index a single file
    python wikem_indexer.py --index-file output/processed/Hyponatremia.md

    # Index all processed markdown files
    python wikem_indexer.py --index-all

    # Check corpus status
    python wikem_indexer.py --status
"""

import argparse
import json
import logging
import os
import time
from pathlib import Path

import google.auth
import google.auth.transport.requests
import requests as http_requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_ID = os.environ.get("PROJECT_ID", "clinical-assistant-457902")
PROJECT_NUMBER = os.environ.get("PROJECT_NUMBER", "930035889332")
RAG_LOCATION = os.environ.get("RAG_LOCATION", "us-west4")

CORPUS_DISPLAY_NAME = "wikem-general-ed"
CORPUS_DESCRIPTION = "General emergency medicine knowledge from WikEM (wikem.org)"

# Paths
OUTPUT_DIR = Path(__file__).parent / "output"
PROCESSED_DIR = OUTPUT_DIR / "processed"
METADATA_DIR = OUTPUT_DIR / "metadata"
CONFIG_PATH = Path(__file__).parent / "wikem_rag_config.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("wikem-indexer")

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
    """Create a new RAG corpus for WikEM content."""
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
    """Get the status of the WikEM corpus."""
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
    """List all files indexed in the WikEM corpus."""
    config = load_config()
    if not config:
        return []

    corpus_name = config["corpus_name"]
    url = f"{BASE_URL}/{corpus_name}/ragFiles"

    resp = http_requests.get(url, headers=api_headers())
    if resp.status_code != 200:
        log.error(f"Failed to list files: {resp.status_code} - {resp.text}")
        return []

    return resp.json().get("ragFiles", [])


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------


def index_file(md_path: Path) -> bool:
    """
    Index a single markdown file into the WikEM RAG corpus.
    Uploads to GCS then imports into RAG corpus.
    """
    config = load_config()
    if not config:
        return False

    corpus_name = config["corpus_name"]

    if not md_path.exists():
        log.error(f"File not found: {md_path}")
        return False

    content = md_path.read_text(encoding="utf-8")
    display_name = md_path.stem  # e.g. "Hyponatremia"

    log.info(f"Indexing {display_name} ({len(content)} chars)...")
    return _index_via_import(corpus_name, md_path, display_name, content)


def _index_via_import(corpus_name: str, md_path: Path, display_name: str, content: str) -> bool:
    """Upload to GCS first, then import into RAG corpus."""
    from google.cloud import storage as gcs

    bucket_name = f"{PROJECT_ID}-wikem"
    gcs_path = f"processed/{display_name}.md"

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
    log.info(f"  Uploaded to {gcs_uri}")

    # Import into RAG corpus
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

    resp = http_requests.post(url, headers=api_headers(), json=payload)

    if resp.status_code not in (200, 201):
        log.error(f"Import failed: {resp.status_code} - {resp.text}")
        return False

    result = resp.json()
    op_name = result.get("name", "")
    if op_name:
        _poll_operation(op_name)

    log.info(f"  ✅ Indexed via GCS import: {display_name}")
    return True


def index_all():
    """Index all processed markdown files."""
    md_files = sorted(PROCESSED_DIR.glob("*.md"))
    if not md_files:
        log.error(f"No markdown files found in {PROCESSED_DIR}")
        return

    log.info(f"Found {len(md_files)} markdown files to index")
    success = 0
    failed = 0

    for md_path in md_files:
        if index_file(md_path):
            success += 1
        else:
            failed += 1

    log.info(f"Indexing complete: {success} success, {failed} failed")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="WikEM RAG Indexer")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--create-corpus", action="store_true", help="Create the WikEM RAG corpus")
    group.add_argument("--index-file", type=str, help="Index a single markdown file")
    group.add_argument("--index-all", action="store_true", help="Index all processed markdown files")
    group.add_argument("--status", action="store_true", help="Check corpus status")
    group.add_argument("--list-files", action="store_true", help="List indexed files")

    args = parser.parse_args()

    if args.create_corpus:
        result = create_corpus()
        if result:
            print(f"\n✅ Corpus created!")
            print(json.dumps(result, indent=2))
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

    elif args.list_files:
        files = list_rag_files()
        if files:
            for f in files:
                print(f"  📄 {f.get('displayName', 'unknown')} — {f.get('name', '')}")
        else:
            print("No files indexed yet")


if __name__ == "__main__":
    main()
