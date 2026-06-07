#!/usr/bin/env python3
"""
Import already-organized GCS batches into existing Vertex AI RAG corpus.
Corpus: 7377459139586293760 (already created, empty)
"""

import json
import time
import google.auth
import google.auth.transport.requests
import requests as http_requests

PROJECT_NUMBER = "930035889332"
RAG_LOCATION = "us-west4"
CORPUS_ID = "7377459139586293760"
GCS_BUCKET = "clinical-assistant-457902-pmc"
CHUNK_SIZE = 1024
CHUNK_OVERLAP = 200

BASE_URL = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}"
CORPUS_NAME = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{CORPUS_ID}"


def get_headers():
    creds, _ = google.auth.default()
    creds.refresh(google.auth.transport.requests.Request())
    return {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}


def poll_operation(op_name, max_wait=3600):
    url = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/{op_name}"
    start = time.time()
    interval = 15
    while time.time() - start < max_wait:
        resp = http_requests.get(url, headers=get_headers())
        if resp.status_code != 200:
            print(f"  Poll error: {resp.status_code} {resp.text}")
            time.sleep(interval)
            continue
        data = resp.json()
        if data.get("done"):
            return data
        elapsed = int(time.time() - start)
        print(f"  ⏳ Waiting... ({elapsed}s)")
        time.sleep(interval)
    print(f"  ⏱️ Timed out after {max_wait}s")
    return None


# Hardcoded batch URIs (already verified: all ≤10K files)
batch_uris = [
    f"gs://{GCS_BUCKET}/processed/batch_00/",  # 7,820 files
    f"gs://{GCS_BUCKET}/processed/batch_01/",  # 10,000 files
    f"gs://{GCS_BUCKET}/processed/batch_02/",  # 10,000 files
    f"gs://{GCS_BUCKET}/processed/batch_03/",  # 10,000 files
    f"gs://{GCS_BUCKET}/processed/batch_04/",  # 10,000 files
    f"gs://{GCS_BUCKET}/processed/batch_05/",  # 8,338 files
]
print(f"Importing {len(batch_uris)} batches into corpus {CORPUS_ID}:")
for uri in batch_uris:
    print(f"  {uri}")

# Check for any running operations first
print("Checking for running operations on corpus...")
check_url = f"{BASE_URL}/ragCorpora/{CORPUS_ID}/operations"
check_resp = http_requests.get(check_url, headers=get_headers())
completed_uris = set()
if check_resp.status_code == 200:
    ops = check_resp.json().get("operations", [])
    for op in ops:
        op_name = op["name"]
        meta = op.get("metadata", {})
        op_uris = meta.get("importRagFilesConfig", {}).get("gcsSource", {}).get("uris", [])
        if op.get("done"):
            # Already completed — skip these URIs
            for u in op_uris:
                completed_uris.add(u)
                print(f"  Already completed: {u}")
        else:
            progress = meta.get("progressPercentage", "?")
            print(f"  Found running op: {op_name.split('/')[-1]}")
            print(f"    URI: {op_uris}, Progress: {progress}%")
            print(f"  Waiting for it to complete...")
            result = poll_operation(op_name)
            if result:
                rm = result.get("metadata", {})
                if rm:
                    print(f"    Metadata: {json.dumps(rm, indent=2)}")
                print(f"  ✅ Running operation completed!")
                for u in op_uris:
                    completed_uris.add(u)
            else:
                print(f"  ❌ Running operation failed/timed out")

if completed_uris:
    print(f"\nSkipping {len(completed_uris)} already-imported batch(es)")

# Import each batch
url = f"{BASE_URL}/ragCorpora/{CORPUS_ID}/ragFiles:import"
all_ok = True

for i, uri in enumerate(batch_uris, 1):
    if uri in completed_uris:
        print(f"\n  Skipping batch {i}/{len(batch_uris)}: {uri} (already imported)")
        continue

    print(f"\n{'='*60}")
    print(f"Importing batch {i}/{len(batch_uris)}: {uri}")
    print(f"{'='*60}")

    payload = {
        "importRagFilesConfig": {
            "gcsSource": {"uris": [uri]},
            "ragFileChunkingConfig": {
                "chunkSize": CHUNK_SIZE,
                "chunkOverlap": CHUNK_OVERLAP,
            },
        }
    }

    resp = http_requests.post(url, headers=get_headers(), json=payload)
    if resp.status_code not in (200, 201):
        print(f"  ❌ Import failed: {resp.status_code} - {resp.text}")
        all_ok = False
        continue

    result = resp.json()
    op_name = result.get("name", "")

    if op_name:
        print(f"  Operation: {op_name.split('/')[-1]}")
        final = poll_operation(op_name)
        if final:
            meta = final.get("metadata", {})
            if meta:
                print(f"  Metadata: {json.dumps(meta, indent=2)}")
            print(f"  ✅ Batch {i}/{len(batch_uris)} complete!")
        else:
            print(f"  ❌ Batch {i}/{len(batch_uris)} failed/timed out")
            all_ok = False
    else:
        print(f"  ❌ No operation returned")
        all_ok = False

print(f"\n{'='*60}")
if all_ok:
    print(f"✅ ALL {len(batch_uris)} BATCHES IMPORTED SUCCESSFULLY")
    print(f"Corpus ID: {CORPUS_ID}")
    print(f"\nNext steps:")
    print(f"  1. Update api/rag_service.py PMC_CORPUS_ID to: {CORPUS_ID}")
    print(f"  2. Redeploy: gcloud run services update em-protocol-api --region us-central1 --project clinical-assistant-457902 --update-env-vars PMC_CORPUS_ID={CORPUS_ID}")
else:
    print("⚠️  Some batches failed — check output above")
