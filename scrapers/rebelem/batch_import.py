#!/usr/bin/env python3
"""
Fast batch import for REBEL EM — uploads all files to GCS in parallel (20 workers),
then submits batch import requests to Vertex AI RAG (25 files per batch).
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import google.auth
import google.auth.transport.requests
import requests as http_requests
from google.cloud import storage

PROJECT_ID = "clinical-assistant-457902"
PROJECT_NUMBER = "930035889332"
RAG_LOCATION = "us-west4"
CORPUS_ID = "1152921504606846976"
BUCKET_NAME = f"{PROJECT_ID}-rebelem"
BASE_URL = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1"
CORPUS_NAME = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{CORPUS_ID}"

PROCESSED_DIR = Path(__file__).parent / "output" / "processed"


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


def upload_all_to_gcs():
    """Upload all .md files to GCS in parallel, also upload metadata."""
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET_NAME)

    # Check what's already uploaded
    existing = set()
    for b in bucket.list_blobs(prefix="processed/"):
        if b.name.endswith(".md"):
            existing.add(b.name.replace("processed/", "").replace(".md", ""))
    print(f"Already in GCS: {len(existing)}")

    all_md = sorted(PROCESSED_DIR.glob("*.md"))
    to_upload = [md for md in all_md if md.stem not in existing]
    print(f"Remaining to upload to GCS: {len(to_upload)}")

    if not to_upload:
        print("All files already in GCS!")
        return

    def upload_one(md_path):
        slug = md_path.stem
        content = md_path.read_text(encoding="utf-8")
        blob = bucket.blob(f"processed/{slug}.md")
        blob.upload_from_string(content, content_type="text/markdown")

        # Also upload metadata
        json_path = PROCESSED_DIR / f"{slug}.json"
        if json_path.exists():
            data = json.load(open(json_path))
            images = data.get("images", [])
            meta = {
                "slug": slug,
                "title": data.get("title", slug),
                "url": data.get("url", f"https://rebelem.com/{slug}/"),
                "author": data.get("author", "Unknown"),
                "reviewer": data.get("reviewer"),
                "categories": data.get("categories", []),
                "tags": data.get("tags", []),
                "date_modified": data.get("date_modified"),
                "description": data.get("description"),
                "word_count": data.get("word_count", 0),
                "citation": data.get("citation", ""),
                "images": [
                    {
                        "url": i.get("url", ""),
                        "alt": i.get("alt", ""),
                        "label": i.get("label", ""),
                        "caption": i.get("caption", ""),
                        "gcs_path": i.get("gcs_path", ""),
                    }
                    for i in images
                    if i.get("url")
                ],
                "license": "CC BY-NC-ND 4.0",
                "source": "REBEL EM",
            }
            meta_blob = bucket.blob(f"metadata/{slug}.json")
            meta_blob.upload_from_string(
                json.dumps(meta, indent=2), content_type="application/json"
            )
        return slug

    start = time.time()
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = {pool.submit(upload_one, md): md.stem for md in to_upload}
        done = 0
        for f in as_completed(futures):
            done += 1
            if done % 100 == 0:
                print(f"  Uploaded {done}/{len(to_upload)}")
    elapsed = time.time() - start
    print(f"Uploaded {done} files + metadata in {elapsed:.1f}s")


def get_all_gcs_uris(indexed):
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
    """Submit batch import requests to Vertex AI RAG."""
    url_import = f"{BASE_URL}/{CORPUS_NAME}/ragFiles:import"
    total_batches = (len(uris) - 1) // batch_size + 1
    submitted = 0

    for i in range(0, len(uris), batch_size):
        batch = uris[i : i + batch_size]
        batch_num = i // batch_size + 1
        payload = {
            "importRagFilesConfig": {
                "gcsSource": {"uris": batch},
                "ragFileChunkingConfig": {"chunkSize": 1024, "chunkOverlap": 200},
            }
        }

        for attempt in range(10):
            resp = http_requests.post(url_import, headers=headers(), json=payload)
            if resp.status_code in (200, 201):
                op = resp.json().get("name", "")
                short_op = op.split("/")[-1][:20] if op else "?"
                print(
                    f"  Batch {batch_num}/{total_batches}: import started ({len(batch)} files) - op:{short_op}"
                )
                submitted += len(batch)
                break
            elif resp.status_code == 400 and "FAILED_PRECONDITION" in resp.text:
                wait = min((2**attempt) * 3, 120)
                print(
                    f"  Batch {batch_num}/{total_batches}: corpus busy, waiting {wait}s (attempt {attempt+1})"
                )
                time.sleep(wait)
            else:
                print(
                    f"  Batch {batch_num}/{total_batches}: ERROR {resp.status_code} - {resp.text[:200]}"
                )
                break

        # Wait between batches for corpus to start processing
        time.sleep(8)

    return submitted


def main():
    print("=== REBEL EM Batch Import ===")
    print()

    # Step 1: Upload all files to GCS
    print("Step 1: Uploading files to GCS...")
    upload_all_to_gcs()
    print()

    # Step 2: Get indexed files
    print("Step 2: Checking already-indexed files...")
    indexed = get_indexed_slugs()
    print(f"Already indexed in corpus: {len(indexed)}")

    # Step 3: Get remaining URIs
    uris = get_all_gcs_uris(indexed)
    print(f"Remaining to index: {len(uris)}")
    print()

    if not uris:
        print("All files already indexed!")
        return

    # Step 3: Batch import
    print(f"Step 3: Submitting {len(uris)} files in batches of 25...")
    start = time.time()
    submitted = batch_import(uris, batch_size=25)
    elapsed = time.time() - start
    print(f"\nDone! Submitted {submitted} files in {elapsed:.0f}s")
    print("Note: Files are being processed asynchronously in the corpus.")
    print("Run 'python rebelem_indexer.py --validate' to check completion.")


if __name__ == "__main__":
    main()
