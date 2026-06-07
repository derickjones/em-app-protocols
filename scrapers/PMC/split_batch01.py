#!/usr/bin/env python3
"""Split batch_01 (17,820 files) into batch_00 (7,820) + batch_01 (10,000)."""

from google.cloud import storage
from concurrent.futures import ThreadPoolExecutor, as_completed

client = storage.Client(project="clinical-assistant-457902")
bucket = client.get_bucket("clinical-assistant-457902-pmc")

print("Listing batch_01 files...")
blobs = sorted(
    b.name for b in bucket.list_blobs(prefix="processed/batch_01/")
    if b.name.endswith(".md")
)
print(f"batch_01 has {len(blobs)} files")

if len(blobs) <= 10000:
    print("Already ≤10K, nothing to do.")
    exit(0)

excess = blobs[10000:]
print(f"Moving {len(excess)} files to batch_00/...")


def move_file(blob_name):
    src = bucket.blob(blob_name)
    dst_name = "processed/batch_00/" + blob_name.split("/")[-1]
    bucket.copy_blob(src, bucket, dst_name)
    src.delete()


with ThreadPoolExecutor(max_workers=20) as pool:
    futures = [pool.submit(move_file, b) for b in excess]
    done = 0
    for f in as_completed(futures):
        f.result()
        done += 1
        if done % 1000 == 0:
            print(f"  {done}/{len(excess)} moved")

print(f"✅ Done! Moved {len(excess)} files to batch_00/")
print(f"batch_00: {len(excess)} files")
print(f"batch_01: {len(blobs) - len(excess)} files")
