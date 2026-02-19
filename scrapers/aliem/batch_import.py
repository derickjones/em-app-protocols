#!/usr/bin/env python3
"""
Fast batch import for ALiEM — uploads all remaining files to GCS in parallel,
then submits batch import requests to Vertex AI RAG (25 files per batch).
"""

import json
import time
from pathlib import Path

import google.auth
import google.auth.transport.requests
import requests as http_requests
from google.cloud import storage

PROJECT_ID = "clinical-assistant-457902"
PROJECT_NUMBER = "930035889332"
RAG_LOCATION = "us-west4"
CORPUS_ID = "4611686018427387904"
BUCKET_NAME = f"{PROJECT_ID}-aliem"
BASE_URL = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1"
CORPUS_NAME = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{CORPUS_ID}"


def get_token():
    creds, _ = google.auth.default()
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def headers():
    return {"Authorization": f"Bearer {get_token()}", "Content-Type": "application/json"}


def get_indexed_slugs():
    """Get set of already-indexed file slugs from the corpus."""
    url = f"{BASE_URL}/{CORPUS_NAME}/ragFiles?pageSize=100"
    indexed = set()
    pt = None
    while True:
        u = url + (f"&pageToken={pt}" if pt else "")
        r = http_requests.get(u, headers=headers())
        data = r.json()
        for f in data.get("ragFiles", []):
            indexed.add(f.get("displayName", "").replace(".md", ""))
        pt = data.get("nextPageToken")
        if not pt:
            break
    return indexed


def get_remaining_uris(indexed):
    """Get GCS URIs for files not yet indexed."""
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET_NAME)
    uris = []
    for b in bucket.list_blobs(prefix="processed/"):
        if b.name.endswith(".md"):
            slug = b.name.replace("processed/", "").replace(".md", "")
            if slug not in indexed:
                uris.append(f"gs://{BUCKET_NAME}/{b.name}")
    return uris


def batch_import(uris, batch_size=25):
    """Submit batch import requests."""
    url_import = f"{BASE_URL}/{CORPUS_NAME}/ragFiles:import"
    total_batches = (len(uris) - 1) // batch_size + 1

    for i in range(0, len(uris), batch_size):
        batch = uris[i : i + batch_size]
        batch_num = i // batch_size + 1
        payload = {
            "importRagFilesConfig": {
                "gcsSource": {"uris": batch},
                "ragFileChunkingConfig": {"chunkSize": 1024, "chunkOverlap": 200},
            }
        }

        for attempt in range(8):
            resp = http_requests.post(url_import, headers=headers(), json=payload)
            if resp.status_code in (200, 201):
                op = resp.json().get("name", "")
                short_op = op.split("/")[-1][:20] if op else "?"
                print(f"  Batch {batch_num}/{total_batches}: import started ({len(batch)} files) - op:{short_op}")
                break
            elif resp.status_code == 400 and "FAILED_PRECONDITION" in resp.text:
                wait = min((2**attempt) * 3, 90)
                print(f"  Batch {batch_num}/{total_batches}: corpus busy, waiting {wait}s (attempt {attempt+1})")
                time.sleep(wait)
            else:
                print(f"  Batch {batch_num}/{total_batches}: ERROR {resp.status_code} - {resp.text[:200]}")
                break

        # Wait between batches for corpus to start processing
        time.sleep(8)


def main():
    print("=== ALiEM Batch Import ===")

    indexed = get_indexed_slugs()
    print(f"Already indexed: {len(indexed)}")

    uris = get_remaining_uris(indexed)
    print(f"Remaining to index: {len(uris)}")

    if not uris:
        print("All files already indexed!")
        return

    start = time.time()
    batch_import(uris, batch_size=25)
    elapsed = time.time() - start
    print(f"\nDone! Submitted {len(uris)} files in {elapsed:.0f}s")
    print("Note: Files are being processed asynchronously in the corpus.")
    print("Run 'python aliem_indexer.py --validate' to check completion.")


if __name__ == "__main__":
    main()
