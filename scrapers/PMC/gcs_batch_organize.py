#!/usr/bin/env python3
"""
One-off script: organize flat GCS processed/*.md files into sub-folders
of ≤10,000 files each so Vertex AI RAG import works.

Handles the partially-reorganized state where batch_01 has ~7833 files
and ~48,338 remain at top level.
"""

import subprocess
import sys
import time

BUCKET = "gs://clinical-assistant-457902-pmc"
PREFIX = "processed"
BATCH_SIZE = 10_000


def run(cmd, timeout=300):
    """Run a shell command and return stdout."""
    print(f"  $ {cmd}")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0 and r.stderr:
        print(f"  stderr: {r.stderr[:500]}")
    return r.stdout.strip()


def count_md(path):
    """Count .md files under a GCS path."""
    out = run(f"gsutil ls {path} 2>/dev/null | grep '\\.md$' | wc -l")
    return int(out.strip())


def list_md(path):
    """List .md files under a GCS path."""
    out = run(f"gsutil ls {path} 2>/dev/null | grep '\\.md$'", timeout=120)
    return [l for l in out.split("\n") if l.endswith(".md")]


def main():
    print("=" * 60)
    print("GCS BATCH ORGANIZE — processed/*.md → batch_XX sub-folders")
    print("=" * 60)
    print()

    # Step 1: Assess current state
    print("[1] Assessing current GCS state...")
    top_level = list_md(f"{BUCKET}/{PREFIX}/")
    # Filter out anything already in a batch_ subfolder
    top_level = [f for f in top_level if "/batch_" not in f]
    print(f"    Top-level .md files: {len(top_level)}")

    # Check existing batches
    existing_batches = {}
    for i in range(1, 10):
        bpath = f"{BUCKET}/{PREFIX}/batch_{i:02d}/"
        n = count_md(bpath)
        if n > 0:
            existing_batches[i] = n
            print(f"    batch_{i:02d}: {n} files")

    total = len(top_level) + sum(existing_batches.values())
    print(f"    Total: {total}")
    print()

    if len(top_level) == 0:
        print("No top-level files to organize. Done!")
        return

    # Step 2: Move batch_01 files back to top level if partially done
    if existing_batches:
        print("[2] Moving partially-batched files back to top level...")
        for batch_num, count in existing_batches.items():
            src = f"{BUCKET}/{PREFIX}/batch_{batch_num:02d}/"
            print(f"    Moving {count} files from batch_{batch_num:02d}/ back to {PREFIX}/")
            run(f"gsutil -m mv '{src}*.md' '{BUCKET}/{PREFIX}/'", timeout=600)
        print()

        # Re-count
        top_level = list_md(f"{BUCKET}/{PREFIX}/")
        top_level = [f for f in top_level if "/batch_" not in f]
        print(f"    After restore: {len(top_level)} top-level files")
        print()

    # Step 3: Create batch folders
    num_batches = (len(top_level) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"[3] Organizing {len(top_level)} files into {num_batches} batches of ≤{BATCH_SIZE}...")
    print()

    for batch_idx in range(num_batches):
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, len(top_level))
        batch_files = top_level[start:end]
        batch_name = f"batch_{batch_idx + 1:02d}"
        dst = f"{BUCKET}/{PREFIX}/{batch_name}/"

        print(f"  [{batch_idx+1}/{num_batches}] Moving {len(batch_files)} files → {batch_name}/")

        # Write file list to a temp file for gsutil
        list_file = f"/tmp/gcs_batch_{batch_name}.txt"
        with open(list_file, "w") as f:
            for uri in batch_files:
                f.write(uri + "\n")

        # Use gsutil -m mv with a file list via cat | gsutil
        # gsutil doesn't have a --from-file, so we use a loop approach
        # Actually, gsutil -m mv supports multiple args but not 10K of them
        # Best approach: use gcloud storage mv which is faster
        t0 = time.time()
        # Move in sub-batches of 500 to avoid arg-too-long
        SUB_BATCH = 500
        for sub_start in range(0, len(batch_files), SUB_BATCH):
            sub_files = batch_files[sub_start:sub_start + SUB_BATCH]
            args = " ".join(f"'{f}'" for f in sub_files)
            run(f"gsutil -m mv {args} {dst}", timeout=300)
            done = min(sub_start + SUB_BATCH, len(batch_files))
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            print(f"    {done}/{len(batch_files)} moved ({rate:.0f}/s)")

        elapsed = time.time() - t0
        print(f"  ✅ {batch_name}: {len(batch_files)} files in {elapsed:.0f}s")
        print()

    print("=" * 60)
    print("✅ REORGANIZATION COMPLETE")
    print("=" * 60)
    print(f"  {num_batches} batch folders created under {BUCKET}/{PREFIX}/")
    print()
    print("Now run the import:")
    print("  python3 pmc_reindex.py --skip-upload")


if __name__ == "__main__":
    main()
