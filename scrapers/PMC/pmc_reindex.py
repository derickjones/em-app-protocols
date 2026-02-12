#!/usr/bin/env python3
"""
PMC RAG Re-Indexer
Rebuilds the PMC Vertex AI RAG corpus from scratch.

Steps:
  1. Upload all processed .md files to GCS (batch)
  2. Delete old RAG corpus (if exists)
  3. Create new RAG corpus
  4. Import all .md files from GCS into the new corpus (single batch import)
  5. Update config file with new corpus ID
  6. Print env var update instructions for Cloud Run

Designed to be re-run every ~6 months when PMC is re-scraped.

Usage:
    # Full rebuild (delete old corpus, create new, upload & index)
    python pmc_reindex.py

    # Upload to GCS only (no corpus changes)
    python pmc_reindex.py --upload-only

    # Skip GCS upload, just rebuild corpus from existing GCS files
    python pmc_reindex.py --skip-upload

    # Dry run — show what would happen
    python pmc_reindex.py --dry-run
"""

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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

GCS_BUCKET_NAME = f"{PROJECT_ID}-pmc"
GCS_PROCESSED_PREFIX = "processed/"

CORPUS_DISPLAY_NAME = "pmc-em-literature"
CORPUS_DESCRIPTION = "Emergency medicine literature from PubMed Central (11 EM journals, 2015-present)"

CHUNK_SIZE = 1024
CHUNK_OVERLAP = 200

# Paths
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output"
PROCESSED_DIR = OUTPUT_DIR / "processed"
CONFIG_PATH = SCRIPT_DIR / "pmc_rag_config.json"

# Vertex AI RAG API
BASE_URL = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1"
PARENT = f"projects/{PROJECT_ID}/locations/{RAG_LOCATION}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pmc-reindex")

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def get_access_token() -> str:
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
# GCS Upload
# ---------------------------------------------------------------------------


def upload_md_files_to_gcs(dry_run: bool = False) -> int:
    """
    Batch upload all .md files from output/processed/ to GCS.
    Uses ThreadPoolExecutor for parallel uploads.
    Returns count of files uploaded.
    """
    md_files = sorted(PROCESSED_DIR.glob("*.md"))
    if not md_files:
        log.error(f"No .md files found in {PROCESSED_DIR}")
        return 0

    log.info(f"Found {len(md_files):,} markdown files to upload to gs://{GCS_BUCKET_NAME}/{GCS_PROCESSED_PREFIX}")

    if dry_run:
        log.info("[DRY RUN] Would upload %d files", len(md_files))
        return len(md_files)

    client = gcs.Client(project=PROJECT_ID)

    # Create bucket if it doesn't exist
    try:
        bucket = client.get_bucket(GCS_BUCKET_NAME)
    except Exception:
        log.info(f"Creating GCS bucket: {GCS_BUCKET_NAME} (location: us-west4)")
        bucket = client.create_bucket(GCS_BUCKET_NAME, location="us-west4")

    uploaded = 0
    errors = 0
    start = time.time()

    def _upload_one(md_path: Path) -> bool:
        try:
            blob = bucket.blob(f"{GCS_PROCESSED_PREFIX}{md_path.name}")
            blob.upload_from_filename(str(md_path), content_type="text/markdown")
            return True
        except Exception as e:
            log.error(f"  ❌ Failed to upload {md_path.name}: {e}")
            return False

    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = {pool.submit(_upload_one, f): f for f in md_files}
        for i, future in enumerate(as_completed(futures), 1):
            if future.result():
                uploaded += 1
            else:
                errors += 1
            if i % 200 == 0 or i == len(md_files):
                elapsed = time.time() - start
                rate = i / elapsed if elapsed > 0 else 0
                log.info(f"  GCS upload: {i}/{len(md_files)} ({rate:.1f}/s) — ✅{uploaded} ❌{errors}")

    elapsed = time.time() - start
    log.info(f"✅ GCS upload complete: {uploaded:,} files in {elapsed:.1f}s ({errors} errors)")
    return uploaded


# ---------------------------------------------------------------------------
# Corpus Management
# ---------------------------------------------------------------------------


def load_config() -> dict:
    """Load existing corpus config if it exists."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def save_config(corpus_name: str, corpus_id: str):
    """Save corpus config for the API and future re-indexing."""
    config = {
        "project_id": PROJECT_ID,
        "project_number": PROJECT_NUMBER,
        "location": RAG_LOCATION,
        "corpus_id": corpus_id,
        "corpus_name": corpus_name,
        "corpus_display_name": CORPUS_DISPLAY_NAME,
        "embedding_model": "text-embedding-005",
        "last_indexed": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    log.info(f"Config saved to {CONFIG_PATH}")


def delete_corpus(corpus_name: str, dry_run: bool = False) -> bool:
    """Delete an existing RAG corpus."""
    if dry_run:
        log.info(f"[DRY RUN] Would delete corpus: {corpus_name}")
        return True

    log.info(f"Deleting corpus: {corpus_name}")
    url = f"{BASE_URL}/{corpus_name}"

    resp = http_requests.delete(url, headers=api_headers(), params={"force": "true"})

    if resp.status_code == 404:
        log.info("  Corpus already deleted or doesn't exist")
        return True

    if resp.status_code not in (200, 201):
        log.error(f"  Failed to delete corpus: {resp.status_code} - {resp.text}")
        return False

    result = resp.json()
    op_name = result.get("name", "")
    if op_name:
        _poll_operation(op_name, description="delete corpus")

    log.info("  ✅ Old corpus deleted")
    return True


def create_corpus(dry_run: bool = False) -> tuple[str, str]:
    """
    Create a new RAG corpus.
    Returns (corpus_name, corpus_id) or ("", "") on failure.
    """
    if dry_run:
        log.info("[DRY RUN] Would create new corpus: %s", CORPUS_DISPLAY_NAME)
        return ("dry-run-corpus", "dry-run-id")

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

    log.info(f"Creating new corpus '{CORPUS_DISPLAY_NAME}'...")
    resp = http_requests.post(url, headers=api_headers(), json=payload)

    if resp.status_code not in (200, 201):
        log.error(f"Failed to create corpus: {resp.status_code} - {resp.text}")
        return ("", "")

    result = resp.json()
    op_name = result.get("name", "")

    if op_name:
        corpus_info = _poll_operation(op_name, description="create corpus")
        if corpus_info:
            corpus_name = corpus_info.get("name", "")
            corpus_id = corpus_name.split("/")[-1] if corpus_name else ""
            log.info(f"  ✅ New corpus created: {corpus_name}")
            return (corpus_name, corpus_id)

    log.error("Failed to get corpus info from operation")
    return ("", "")


def import_gcs_to_corpus(corpus_name: str, dry_run: bool = False) -> bool:
    """
    Batch import all .md files from GCS into the RAG corpus.
    Uses a single wildcard GCS URI to import the entire processed/ prefix.
    """
    gcs_uri = f"gs://{GCS_BUCKET_NAME}/{GCS_PROCESSED_PREFIX}"

    if dry_run:
        log.info(f"[DRY RUN] Would import {gcs_uri}*.md into {corpus_name}")
        return True

    log.info(f"Importing from {gcs_uri} into corpus...")

    url = f"{BASE_URL}/{corpus_name}/ragFiles:import"

    payload = {
        "importRagFilesConfig": {
            "gcsSource": {
                "uris": [gcs_uri]
            },
            "ragFileChunkingConfig": {
                "chunkSize": CHUNK_SIZE,
                "chunkOverlap": CHUNK_OVERLAP,
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
        log.info(f"  Import operation started: {op_name.split('/')[-1]}")
        import_result = _poll_operation(op_name, description="import files", max_wait=3600)
        if import_result:
            metadata = import_result.get("metadata", {})
            if metadata:
                log.info(f"  Import metadata: {json.dumps(metadata, indent=2)}")
            log.info("  ✅ Batch import complete")
            return True
        else:
            log.error("  Import operation failed or timed out")
            return False

    log.warning("No operation returned — import may have failed")
    return False


# ---------------------------------------------------------------------------
# Operation Polling
# ---------------------------------------------------------------------------


def _poll_operation(op_name: str, description: str = "operation", max_wait: int = 300) -> dict | None:
    """Poll a long-running operation until it completes."""
    if op_name.startswith("projects/"):
        url = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/{op_name}"
    else:
        url = f"{BASE_URL}/{op_name}"

    start = time.time()
    poll_interval = 5

    while time.time() - start < max_wait:
        resp = http_requests.get(url, headers=api_headers())
        if resp.status_code != 200:
            log.error(f"  Poll failed for {description}: {resp.status_code}")
            return None

        data = resp.json()
        if data.get("done"):
            if "error" in data:
                log.error(f"  {description} failed: {data['error']}")
                return None
            return data.get("response", data)

        elapsed = int(time.time() - start)
        log.info(f"  ⏳ Waiting for {description}... ({elapsed}s)")

        time.sleep(poll_interval)
        if elapsed > 60:
            poll_interval = 15
        elif elapsed > 30:
            poll_interval = 10

    log.error(f"  {description} timed out after {max_wait}s")
    return None


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------


def reindex(
    skip_upload: bool = False,
    upload_only: bool = False,
    dry_run: bool = False,
):
    """
    Full re-index pipeline:
      1. Upload .md files to GCS
      2. Delete old corpus
      3. Create new corpus
      4. Batch import from GCS
      5. Save config + print instructions
    """
    print()
    print("=" * 70)
    print("📚 PMC RAG RE-INDEX")
    print("=" * 70)
    if dry_run:
        print("  ⚠️  DRY RUN — no changes will be made")
    print()

    # -------------------------------------------------------------------
    # Step 1: Upload to GCS
    # -------------------------------------------------------------------
    if not skip_upload:
        log.info("STEP 1/4: Uploading .md files to GCS...")
        uploaded = upload_md_files_to_gcs(dry_run=dry_run)
        if uploaded == 0:
            log.error("No files uploaded — aborting")
            return
        print()
    else:
        log.info("STEP 1/4: Skipping GCS upload (--skip-upload)")
        print()

    if upload_only:
        log.info("Upload complete (--upload-only). Stopping here.")
        return

    # -------------------------------------------------------------------
    # Step 2: Delete old corpus
    # -------------------------------------------------------------------
    log.info("STEP 2/4: Deleting old corpus...")
    old_config = load_config()
    if old_config and old_config.get("corpus_name"):
        old_corpus_name = old_config["corpus_name"]
        old_corpus_id = old_config.get("corpus_id", "?")
        log.info(f"  Old corpus: {old_corpus_id}")
        if not delete_corpus(old_corpus_name, dry_run=dry_run):
            log.error("Failed to delete old corpus — aborting")
            return
    else:
        log.info("  No existing corpus config found, skipping delete")
    print()

    # -------------------------------------------------------------------
    # Step 3: Create new corpus
    # -------------------------------------------------------------------
    log.info("STEP 3/4: Creating new corpus...")
    corpus_name, corpus_id = create_corpus(dry_run=dry_run)
    if not corpus_name:
        log.error("Failed to create new corpus — aborting")
        return
    print()

    # -------------------------------------------------------------------
    # Step 4: Batch import from GCS
    # -------------------------------------------------------------------
    log.info("STEP 4/4: Importing files from GCS into corpus...")
    success = import_gcs_to_corpus(corpus_name, dry_run=dry_run)
    print()

    # -------------------------------------------------------------------
    # Save config
    # -------------------------------------------------------------------
    if not dry_run:
        save_config(corpus_name, corpus_id)

    # -------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------
    print("=" * 70)
    print("📚 PMC RE-INDEX COMPLETE")
    print("=" * 70)
    print(f"  Corpus Name:  {corpus_name}")
    print(f"  Corpus ID:    {corpus_id}")
    print(f"  GCS Bucket:   gs://{GCS_BUCKET_NAME}/{GCS_PROCESSED_PREFIX}")
    print(f"  Config:       {CONFIG_PATH}")
    print(f"  Import:       {'✅ Success' if success else '❌ Failed'}")
    print()

    if not dry_run and corpus_id:
        print("⚠️  UPDATE Cloud Run env var with new corpus ID:")
        print(f"  gcloud run services update em-protocol-api \\")
        print(f"    --region us-central1 \\")
        print(f"    --update-env-vars PMC_CORPUS_ID={corpus_id}")
        print()
        print("  Or set it in the Cloud Console:")
        print(f"  PMC_CORPUS_ID = {corpus_id}")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="PMC RAG Re-Indexer — rebuild the corpus from scratch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full rebuild
  python pmc_reindex.py

  # Upload .md files to GCS only
  python pmc_reindex.py --upload-only

  # Rebuild corpus from existing GCS files (skip upload)
  python pmc_reindex.py --skip-upload

  # Preview what would happen
  python pmc_reindex.py --dry-run
        """,
    )
    parser.add_argument("--upload-only", action="store_true",
                        help="Only upload .md files to GCS, don't touch the corpus")
    parser.add_argument("--skip-upload", action="store_true",
                        help="Skip GCS upload, rebuild corpus from existing GCS files")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without making changes")

    args = parser.parse_args()

    if args.upload_only and args.skip_upload:
        parser.error("Cannot use --upload-only and --skip-upload together")

    reindex(
        skip_upload=args.skip_upload,
        upload_only=args.upload_only,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
