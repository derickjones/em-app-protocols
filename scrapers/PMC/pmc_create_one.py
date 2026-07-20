#!/usr/bin/env python3
"""
Phase 1 of the curated-3-corpus plan (docs/pmc-sharding-workstream.md revision):
create and import ONE test corpus (pmc-em) before building anything else, to
verify whether a single freshly-created corpus (vs. 9 simultaneous ones) behaves
differently on the shared Basic-tier Spanner instance.

Source: gs://clinical-assistant-457902-pmc/processed/shard_00/ — this already
IS the Emergency Medicine group's 6,960 files, unmodified, from the first
(superseded) 9-shard attempt. No new GCS reorganization needed for this step.

Usage:
    python3 pmc_create_one.py
"""

import json
import time

import google.auth
import google.auth.transport.requests
import requests as http_requests

PROJECT_ID = "clinical-assistant-457902"
PROJECT_NUMBER = "930035889332"
RAG_LOCATION = "us-west4"
GCS_BUCKET_NAME = f"{PROJECT_ID}-pmc"
BASE_URL = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1"
PARENT = f"projects/{PROJECT_ID}/locations/{RAG_LOCATION}"

DISPLAY_NAME = "pmc-em"
DESCRIPTION = (
    "PMC Emergency Medicine literature (curated, single-corpus test — "
    "see docs/pmc-sharding-workstream.md revision). 12 EM-specific journals, "
    "6,960 files."
)
SOURCE_GCS_URI = f"gs://{GCS_BUCKET_NAME}/processed/shard_00/"


def get_access_token() -> str:
    credentials, _ = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token


def headers() -> dict:
    return {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}


def poll(op_name: str, description: str, max_wait: int = 600):
    url = f"{BASE_URL}/{op_name}"
    start = time.time()
    interval = 10
    while time.time() - start < max_wait:
        resp = http_requests.get(url, headers=headers())
        if resp.status_code != 200:
            print(f"  poll error: {resp.status_code} {resp.text[:200]}")
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


def main():
    print(f"Creating corpus '{DISPLAY_NAME}'...")
    payload = {
        "display_name": DISPLAY_NAME,
        "description": DESCRIPTION,
        "rag_embedding_model_config": {
            "vertex_prediction_endpoint": {
                "endpoint": f"projects/{PROJECT_ID}/locations/{RAG_LOCATION}/publishers/google/models/text-embedding-005"
            }
        },
    }
    url = f"{BASE_URL}/{PARENT}/ragCorpora"
    resp = http_requests.post(url, headers=headers(), json=payload)
    if resp.status_code not in (200, 201):
        print(f"❌ Create failed: {resp.status_code} {resp.text[:300]}")
        return
    op_name = resp.json().get("name", "")
    result = poll(op_name, "create corpus", max_wait=300)
    if not result:
        return
    corpus_name = result.get("name", "")
    corpus_id = corpus_name.split("/")[-1]
    print(f"✅ Created: {corpus_id}")

    print(f"\nImporting {SOURCE_GCS_URI} ...")
    import_url = f"{BASE_URL}/{corpus_name}/ragFiles:import"
    import_payload = {
        "importRagFilesConfig": {
            "gcsSource": {"uris": [SOURCE_GCS_URI]},
            "ragFileChunkingConfig": {"chunkSize": 1024, "chunkOverlap": 200},
        }
    }
    resp2 = http_requests.post(import_url, headers=headers(), json=import_payload)
    if resp2.status_code not in (200, 201):
        print(f"❌ Import failed: {resp2.status_code} {resp2.text[:300]}")
        return
    op_name2 = resp2.json().get("name", "")
    result2 = poll(op_name2, "import", max_wait=1800)
    if result2:
        meta = result2.get("metadata", {}).get("genericMetadata", {})
        failures = meta.get("partialFailures", [])
        if failures:
            print(f"  ⚠️  {len(failures)} partial failures")
        print("✅ Import complete")

    # Verify count
    check = http_requests.get(f"{BASE_URL}/{corpus_name}", headers=headers())
    count = check.json().get("ragFilesCount") if check.status_code == 200 else None
    print(f"\nragFilesCount: {count} (expected 6960)")

    with open("pmc_em_corpus_id.txt", "w") as f:
        f.write(corpus_id)
    print(f"\nCorpus ID saved to pmc_em_corpus_id.txt: {corpus_id}")


if __name__ == "__main__":
    main()
