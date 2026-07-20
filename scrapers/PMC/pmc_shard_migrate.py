#!/usr/bin/env python3
"""
PMC Shard Migration (Phase 2 of docs/pmc-sharding-workstream.md)

Reads pmc_shard_registry.json + pmc_shard_assignments.json (written by
pmc_shard.py --write), then:
  1. Moves each PMC .md file from its current processed/batch_XX/ location into
     processed/{shard_id}/ — filenames preserved exactly, metadata/ untouched.
  2. Creates one KNN RAG corpus per shard in us-west4 (same backend as every
     other corpus — this does NOT touch ANN/Vector Search/us-central1).
  3. Imports each shard's GCS folder into its corpus.
  4. Writes real corpus IDs back into the registry.

Does NOT touch the live PMC corpus (7377459139586293760) or metadata/*.json.
Safe to re-run: skips already-moved files and already-created/imported shards,
so an interruption can be resumed by just running again.

Usage:
    python3 pmc_shard_migrate.py --dry-run     # print plan, touch nothing
    python3 pmc_shard_migrate.py               # full run (move + create + import)
    python3 pmc_shard_migrate.py --skip-move   # corpora/import only (files already moved)
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import google.auth
import google.auth.transport.requests
import requests as http_requests
from google.cloud import storage as gcs

PROJECT_ID = "clinical-assistant-457902"
PROJECT_NUMBER = "930035889332"
RAG_LOCATION = "us-west4"
GCS_BUCKET_NAME = f"{PROJECT_ID}-pmc"
GCS_PROCESSED_PREFIX = "processed/"

SCRIPT_DIR = Path(__file__).parent
REGISTRY_PATH = SCRIPT_DIR / "pmc_shard_registry.json"
ASSIGNMENTS_PATH = SCRIPT_DIR / "pmc_shard_assignments.json"

BASE_URL = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1"
PARENT = f"projects/{PROJECT_ID}/locations/{RAG_LOCATION}"

LIVE_PMC_CORPUS_ID = "7377459139586293760"  # must never be touched by this script


def get_access_token() -> str:
    credentials, _ = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token


def api_headers() -> dict:
    return {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}


def load_state():
    registry = json.loads(REGISTRY_PATH.read_text())
    assignments = json.loads(ASSIGNMENTS_PATH.read_text())
    return registry, assignments


def save_registry(registry):
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2))


# ---------------------------------------------------------------------------
# Step 1: GCS reorganization
# ---------------------------------------------------------------------------


def build_current_location_map(bucket) -> dict:
    """Map pmcid -> current full blob name, from whatever's under processed/
    today (batch_00..batch_05), excluding metadata/. One list call for all ~56K."""
    print("Listing current processed/*.md locations...")
    mapping = {}
    for blob in bucket.list_blobs(prefix=GCS_PROCESSED_PREFIX):
        if not blob.name.endswith(".md"):
            continue
        filename = blob.name.split("/")[-1]
        pmcid = filename.replace(".md", "")
        mapping[pmcid] = blob.name
    print(f"  Found {len(mapping):,} .md files currently in processed/")
    return mapping


def move_shard_files(bucket, shard_id: str, pmcids: list, current_map: dict, dry_run: bool) -> tuple:
    """Move (copy+delete) each pmcid's .md into processed/{shard_id}/. Skips
    files already at the destination (resumable). Returns (moved, skipped, missing)."""
    dest_prefix = f"{GCS_PROCESSED_PREFIX}{shard_id}/"
    moved, skipped, missing = 0, 0, 0
    to_move = []

    for pmcid in pmcids:
        dest_name = f"{dest_prefix}{pmcid}.md"
        src_name = current_map.get(pmcid)
        if src_name is None:
            missing += 1
            continue
        if src_name == dest_name:
            skipped += 1  # already in place from a prior run
            continue
        to_move.append((src_name, dest_name))

    if missing:
        print(f"  ⚠️  {shard_id}: {missing} pmcids not found in current GCS listing")

    if dry_run:
        print(f"  [DRY RUN] {shard_id}: would move {len(to_move)}, skip {skipped} already-placed")
        return len(to_move), skipped, missing

    if not to_move:
        print(f"  {shard_id}: nothing to move ({skipped} already in place)")
        return 0, skipped, missing

    def _copy_and_delete(pair):
        src_name, dest_name = pair
        src_blob = bucket.blob(src_name)
        # Skip if destination already exists (resumability, avoids duplicate work)
        dest_blob = bucket.blob(dest_name)
        if dest_blob.exists():
            return "skipped"
        bucket.copy_blob(src_blob, bucket, dest_name)
        src_blob.delete()
        return "moved"

    start = time.time()
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = [pool.submit(_copy_and_delete, pair) for pair in to_move]
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            if result == "moved":
                moved += 1
            else:
                skipped += 1
            if i % 2000 == 0 or i == len(to_move):
                elapsed = time.time() - start
                rate = i / elapsed if elapsed > 0 else 0
                print(f"    {shard_id}: {i}/{len(to_move)} ({rate:.0f}/s)")

    print(f"  ✅ {shard_id}: moved {moved}, skipped {skipped} (already placed), missing {missing}")
    return moved, skipped, missing


# ---------------------------------------------------------------------------
# Step 2/3: Corpus create + import (mirrors pmc_reindex.py's proven helpers)
# ---------------------------------------------------------------------------


def _poll_operation(op_name: str, description: str, max_wait: int = 3600) -> dict | None:
    if op_name.startswith("projects/"):
        url = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/{op_name}"
    else:
        url = f"{BASE_URL}/{op_name}"

    start = time.time()
    interval = 15
    while time.time() - start < max_wait:
        resp = http_requests.get(url, headers=api_headers())
        if resp.status_code != 200:
            print(f"  Poll error for {description}: {resp.status_code} {resp.text[:200]}")
            time.sleep(interval)
            continue
        data = resp.json()
        if data.get("done"):
            if "error" in data:
                print(f"  ❌ {description} failed: {data['error']}")
                return None
            return data.get("response", data)
        elapsed = int(time.time() - start)
        print(f"  ⏳ {description}... ({elapsed}s)")
        time.sleep(interval)
    print(f"  ⏱️ {description} timed out after {max_wait}s")
    return None


def create_shard_corpus(shard: dict) -> str | None:
    """Create one KNN corpus for a shard. Returns corpus_id, or None on failure."""
    display_name = f"pmc-{shard['id']}"
    journals_preview = ", ".join(shard["journals"][:3])
    if len(shard["journals"]) > 3:
        journals_preview += f" +{len(shard['journals']) - 3} more"
    description = (
        f"PMC literature shard ({shard['ui_group']}): {journals_preview}. "
        f"Part of the sharded PMC corpus — see docs/pmc-sharding-workstream.md."
    )

    payload = {
        "display_name": display_name,
        "description": description,
        "rag_embedding_model_config": {
            "vertex_prediction_endpoint": {
                "endpoint": f"projects/{PROJECT_ID}/locations/{RAG_LOCATION}/publishers/google/models/text-embedding-005"
            }
        },
    }

    print(f"Creating corpus for {shard['id']} ({display_name})...")
    url = f"{BASE_URL}/{PARENT}/ragCorpora"
    resp = http_requests.post(url, headers=api_headers(), json=payload)
    if resp.status_code not in (200, 201):
        print(f"  ❌ Failed to create corpus: {resp.status_code} {resp.text[:300]}")
        return None

    op_name = resp.json().get("name", "")
    result = _poll_operation(op_name, f"create corpus {shard['id']}", max_wait=300)
    if not result:
        return None
    corpus_name = result.get("name", "")
    corpus_id = corpus_name.split("/")[-1] if corpus_name else None
    if corpus_id:
        print(f"  ✅ {shard['id']} -> corpus {corpus_id}")
    return corpus_id


def import_shard(shard: dict) -> bool:
    """Import gs://bucket/processed/{shard_id}/ into the shard's corpus."""
    corpus_id = shard["corpus_id"]
    corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{corpus_id}"
    gcs_uri = f"gs://{GCS_BUCKET_NAME}/{GCS_PROCESSED_PREFIX}{shard['id']}/"

    # Check for already-running or already-completed import ops (resumability,
    # same pattern as import_to_corpus.py).
    check_url = f"{BASE_URL}/{corpus_name}/operations"
    check_resp = http_requests.get(check_url, headers=api_headers())
    if check_resp.status_code == 200:
        for op in check_resp.json().get("operations", []):
            meta = op.get("metadata", {})
            op_uris = meta.get("importRagFilesConfig", {}).get("gcsSource", {}).get("uris", [])
            if gcs_uri in op_uris:
                if op.get("done"):
                    print(f"  {shard['id']}: import already completed")
                    return True
                print(f"  {shard['id']}: import already running, waiting...")
                result = _poll_operation(op["name"], f"import {shard['id']} (existing op)")
                return result is not None

    print(f"Importing {gcs_uri} into corpus {corpus_id} ({shard['id']})...")
    url = f"{BASE_URL}/{corpus_name}/ragFiles:import"
    payload = {
        "importRagFilesConfig": {
            "gcsSource": {"uris": [gcs_uri]},
            "ragFileChunkingConfig": {"chunkSize": 1024, "chunkOverlap": 200},
        }
    }
    resp = http_requests.post(url, headers=api_headers(), json=payload)
    if resp.status_code not in (200, 201):
        print(f"  ❌ Import failed for {shard['id']}: {resp.status_code} {resp.text[:300]}")
        return False

    op_name = resp.json().get("name", "")
    result = _poll_operation(op_name, f"import {shard['id']}")
    if result:
        print(f"  ✅ {shard['id']} import complete")
        return True
    return False


def get_corpus_file_count(corpus_id: str) -> int | None:
    corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{corpus_id}"
    resp = http_requests.get(f"{BASE_URL}/{corpus_name}", headers=api_headers())
    if resp.status_code != 200:
        return None
    return resp.json().get("ragFilesCount")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-move", action="store_true", help="Skip GCS reorg, assume files already moved")
    args = parser.parse_args()

    registry, assignments = load_state()
    client = gcs.Client(project=PROJECT_ID)
    bucket = client.bucket(GCS_BUCKET_NAME)

    # --- Step 1: GCS reorganization ---
    if not args.skip_move:
        print("\n" + "=" * 70)
        print("STEP 1: Reorganize GCS files into shard folders")
        print("=" * 70)
        current_map = build_current_location_map(bucket)
        for shard in registry["shards"]:
            pmcids = assignments[shard["id"]]
            move_shard_files(bucket, shard["id"], pmcids, current_map, args.dry_run)
            # Refresh map incrementally isn't necessary — moved files won't be
            # revisited since each pmcid belongs to exactly one shard.
    else:
        print("Skipping GCS reorg (--skip-move)")

    if args.dry_run:
        print("\n[DRY RUN] Stopping before corpus creation/import.")
        return

    # --- Step 2 + 3: Create corpora + import ---
    print("\n" + "=" * 70)
    print("STEP 2/3: Create corpora + import shard folders")
    print("=" * 70)

    for shard in registry["shards"]:
        if shard["corpus_id"] is None:
            corpus_id = create_shard_corpus(shard)
            if not corpus_id:
                print(f"❌ Aborting: failed to create corpus for {shard['id']}")
                save_registry(registry)
                return
            shard["corpus_id"] = corpus_id
            save_registry(registry)  # persist immediately, resumable
        else:
            print(f"{shard['id']}: corpus already created ({shard['corpus_id']})")

    for shard in registry["shards"]:
        ok = import_shard(shard)
        if not ok:
            print(f"❌ Import failed for {shard['id']} — stopping. Re-run to retry (resumable).")
            return

    # --- Verification ---
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    total = 0
    all_ok = True
    for shard in registry["shards"]:
        count = get_corpus_file_count(shard["corpus_id"])
        expected = shard["file_count"]
        status = "✅" if count == expected else "⚠️ MISMATCH"
        if count != expected:
            all_ok = False
        print(f"  {shard['id']}: expected={expected} actual={count} {status}")
        total += count or 0

    print(f"\nTotal across all shards: {total:,} (expected 56,156)")
    live_check = get_corpus_file_count(LIVE_PMC_CORPUS_ID)
    print(f"Live PMC corpus untouched check: {live_check:,} files (expected 56,156)")

    if all_ok and total == 56156 and live_check == 56156:
        print("\n✅ PHASE 2 COMPLETE — all shards match, live corpus untouched.")
    else:
        print("\n⚠️  Discrepancies found — review before proceeding to Phase 3.")


if __name__ == "__main__":
    main()
