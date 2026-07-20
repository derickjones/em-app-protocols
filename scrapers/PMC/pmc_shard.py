#!/usr/bin/env python3
"""
PMC Shard Planner (Phase 1 of docs/pmc-sharding-workstream.md)

Reads per-article journal metadata from GCS, groups journals into UI groups
(mirroring frontend/app/page.tsx's PMC_JOURNAL_GROUPS), and bin-packs them into
shards capped at TARGET_CAP files each (well under Vertex's 10K-file KNN
performance threshold).

Dry-run by default: prints the plan, writes nothing. Pass --write to persist
pmc_shard_registry.json and pmc_shard_assignments.json.

Usage:
    python3 pmc_shard.py                 # dry run, uses cached manifest if present
    python3 pmc_shard.py --refresh       # re-read all metadata from GCS (slow)
    python3 pmc_shard.py --write         # write registry + assignments files
"""

import argparse
import json
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from google.cloud import storage as gcs

PROJECT_ID = "clinical-assistant-457902"
BUCKET_NAME = f"{PROJECT_ID}-pmc"
RAG_LOCATION = "us-west4"
TARGET_CAP = 7500
RESHARD_WATERMARK = 8500
EMBEDDING_MODEL = "text-embedding-005"
CHUNK_SIZE = 1024
CHUNK_OVERLAP = 200

SCRIPT_DIR = Path(__file__).parent
MANIFEST_CACHE = SCRIPT_DIR / "pmc_journal_manifest.json"
REGISTRY_PATH = SCRIPT_DIR / "pmc_shard_registry.json"
ASSIGNMENTS_PATH = SCRIPT_DIR / "pmc_shard_assignments.json"

# Mirrors frontend/app/page.tsx PMC_JOURNAL_GROUPS (journal key -> UI group).
# Counts here are from the April 2026 scrape and used only for a sanity
# cross-check against live GCS counts — the live count is authoritative.
UI_GROUPS = {
    "Emergency Medicine": {
        "The Western Journal of Emergency Medicine": 2066,
        "Journal of the American College of Emergency Physicians Open": 1587,
        "The American Journal of Emergency Medicine": 877,
        "Annals of Emergency Medicine": 674,
        "Acad Emerg Med": 590,
        "The Journal of Emergency Medicine": 259,
        "Pediatric Emergency Care": 246,
        "CJEM": 212,
        "Advanced Journal of Emergency Medicine": 146,
        "Prehospital Emergency Care": 111,
        "Eur J Emerg Med": 108,
        "Air Medical Journal": 86,
    },
    "Critical Care & Resuscitation": {
        "Am J Respir Crit Care Med": 4464,
        "Chest": 2838,
        "Crit Care Med": 1469,
        "Resuscitation Plus": 1205,
        "Shock": 691,
        "Resuscitation": 525,
        "J Intensive Care Med": 244,
    },
    "JAMA Family": {
        "JAMA Netw Open": 9943,
        "JAMA": 3284,
        "JAMA Intern Med": 2149,
        "JAMA Oncol": 1881,
        "JAMA Pediatr": 1827,
        "JAMA Surg": 1551,
        "JAMA Neurol": 1511,
        "JAMA Ophthalmol": 1458,
        "JAMA Cardiol": 1335,
        "JAMA Otolaryngol Head Neck Surg": 1169,
    },
    "High-Impact General": {
        "Lancet": 2667,
        "BMJ": 2598,
        "N Engl J Med": 1822,
        "Lancet Infect Dis": 1619,
        "Ann Intern Med": 1046,
        "Lancet Respir Med": 821,
        "Mayo Clin Proc": 719,
        "Lancet Neurol": 360,
    },
}

JOURNAL_TO_GROUP = {
    journal: group for group, journals in UI_GROUPS.items() for journal in journals
}


def build_manifest(refresh: bool) -> dict:
    """Return {pmcid: journal}, reading from GCS metadata/*.json (parallel)."""
    if not refresh and MANIFEST_CACHE.exists():
        print(f"Using cached manifest: {MANIFEST_CACHE}")
        return json.loads(MANIFEST_CACHE.read_text())

    print("Reading metadata/*.json from GCS (parallel, this can take a while)...")
    client = gcs.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET_NAME)
    blobs = list(bucket.list_blobs(prefix="metadata/"))
    blobs = [b for b in blobs if b.name.endswith(".json")]
    print(f"  Found {len(blobs):,} metadata files")

    manifest = {}
    errors = 0

    def _read_one(blob):
        try:
            data = json.loads(blob.download_as_bytes())
            pmcid = data.get("protocol_id") or blob.name.split("/")[-1].replace(".json", "")
            journal = data.get("journal", "")
            return pmcid, journal
        except Exception as e:
            return None, str(e)

    start = time.time()
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = {pool.submit(_read_one, b): b for b in blobs}
        for i, future in enumerate(as_completed(futures), 1):
            pmcid, journal = future.result()
            if pmcid:
                manifest[pmcid] = journal
            else:
                errors += 1
            if i % 5000 == 0 or i == len(blobs):
                elapsed = time.time() - start
                rate = i / elapsed if elapsed > 0 else 0
                print(f"  {i:,}/{len(blobs):,} ({rate:.0f}/s, {errors} errors)")

    MANIFEST_CACHE.write_text(json.dumps(manifest, indent=0))
    print(f"Manifest cached to {MANIFEST_CACHE} ({len(manifest):,} entries, {errors} errors)")
    return manifest


def bin_pack_group(journal_counts: dict, pmcids_by_journal: dict, group_name: str, cap: int) -> list:
    """
    First-fit-decreasing bin-pack for one UI group. Returns list of shard dicts:
    {journals: [...], file_count: N, pmcids: [...]}.
    A journal larger than `cap` is split across consecutive shards on its own.
    """
    shards = []
    sorted_journals = sorted(journal_counts.items(), key=lambda kv: -kv[1])

    for journal, count in sorted_journals:
        pmcids = pmcids_by_journal[journal]

        if count > cap:
            # Split this single oversized journal across its own dedicated shards.
            for i in range(0, len(pmcids), cap):
                chunk = pmcids[i:i + cap]
                shards.append({
                    "journals": [journal],
                    "file_count": len(chunk),
                    "pmcids": chunk,
                })
            continue

        # First-fit: find an existing shard in this group with room.
        placed = False
        for shard in shards:
            if shard["file_count"] + count <= cap:
                shard["journals"].append(journal)
                shard["file_count"] += count
                shard["pmcids"].extend(pmcids)
                placed = True
                break
        if not placed:
            shards.append({
                "journals": [journal],
                "file_count": count,
                "pmcids": list(pmcids),
            })

    for s in shards:
        s["ui_group"] = group_name
    return shards


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Re-read metadata from GCS instead of using cache")
    parser.add_argument("--write", action="store_true", help="Write registry + assignments files (default: dry run)")
    args = parser.parse_args()

    manifest = build_manifest(refresh=args.refresh)

    # Group pmcids by journal
    pmcids_by_journal = defaultdict(list)
    unknown_journal = 0
    for pmcid, journal in manifest.items():
        if journal not in JOURNAL_TO_GROUP:
            unknown_journal += 1
            continue
        pmcids_by_journal[journal].append(pmcid)

    if unknown_journal:
        print(f"\n⚠️  {unknown_journal} files have a journal not in the known UI_GROUPS mapping (excluded from packing)")

    live_counts = {j: len(pmcids) for j, pmcids in pmcids_by_journal.items()}

    # Sanity cross-check vs. the April-2026 scrape counts baked into UI_GROUPS
    print("\n=== Live vs. baseline journal counts (sanity check) ===")
    for group, journals in UI_GROUPS.items():
        for journal, baseline_count in journals.items():
            live = live_counts.get(journal, 0)
            flag = "" if live == baseline_count else "  ⚠️ DIFFERS"
            if flag:
                print(f"  [{group}] {journal}: baseline={baseline_count} live={live}{flag}")

    # Bin-pack per UI group
    all_shards = []
    for group_name, journals in UI_GROUPS.items():
        group_counts = {j: live_counts.get(j, 0) for j in journals if live_counts.get(j, 0) > 0}
        if not group_counts:
            continue
        group_shards = bin_pack_group(group_counts, pmcids_by_journal, group_name, TARGET_CAP)
        all_shards.extend(group_shards)

    # Assign shard IDs
    for i, shard in enumerate(all_shards):
        shard["id"] = f"shard_{i:02d}"

    # Build registry + assignments
    journal_to_shards = defaultdict(list)
    for shard in all_shards:
        for j in shard["journals"]:
            journal_to_shards[j].append(shard["id"])

    ui_groups_out = [
        {
            "group": group,
            "journals": [
                {"key": j, "count": live_counts.get(j, 0)}
                for j in journals
            ],
        }
        for group, journals in UI_GROUPS.items()
    ]

    registry = {
        "target_cap": TARGET_CAP,
        "reshard_watermark": RESHARD_WATERMARK,
        "location": RAG_LOCATION,
        "embedding_model": EMBEDDING_MODEL,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "shards": [
            {
                "id": s["id"],
                "corpus_id": None,
                "file_count": s["file_count"],
                "ui_group": s["ui_group"],
                "journals": s["journals"],
            }
            for s in all_shards
        ],
        "journal_to_shards": dict(journal_to_shards),
        "ui_groups": ui_groups_out,
    }

    assignments = {s["id"]: s["pmcids"] for s in all_shards}

    # ---- Report ----
    total_files = sum(s["file_count"] for s in all_shards)
    print(f"\n=== SHARD PLAN ({len(all_shards)} shards, target cap {TARGET_CAP}, hard limit 10,000) ===\n")
    print(f"{'Shard':10s} {'UI Group':32s} {'Files':>7s}  Journals")
    for s in all_shards:
        over = " ⚠️ OVER 10K" if s["file_count"] > 10000 else (" ⚠️ over cap" if s["file_count"] > TARGET_CAP else "")
        journals_str = ", ".join(s["journals"][:2]) + (f" +{len(s['journals'])-2} more" if len(s["journals"]) > 2 else "")
        print(f"{s['id']:10s} {s['ui_group']:32s} {s['file_count']:7,d}{over}  {journals_str}")

    print(f"\nTotal files across all shards: {total_files:,}")
    print(f"Total files in manifest:       {len(manifest):,}")
    print(f"Difference:                    {len(manifest) - total_files:,} (excluded/unknown-journal files)")

    max_shard = max(s["file_count"] for s in all_shards)
    print(f"\nLargest shard: {max_shard:,} files ({'OK, under cap' if max_shard <= TARGET_CAP else 'OVER TARGET CAP'})")

    if args.write:
        REGISTRY_PATH.write_text(json.dumps(registry, indent=2))
        ASSIGNMENTS_PATH.write_text(json.dumps(assignments, indent=0))
        print(f"\n✅ Written: {REGISTRY_PATH}")
        print(f"✅ Written: {ASSIGNMENTS_PATH}")
    else:
        print("\n(dry run — pass --write to persist pmc_shard_registry.json + pmc_shard_assignments.json)")


if __name__ == "__main__":
    main()
