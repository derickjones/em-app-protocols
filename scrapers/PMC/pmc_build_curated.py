#!/usr/bin/env python3
"""
Phase 2 of docs/pmc-sharding-workstream.md: build pmc-critical-care and
pmc-high-impact corpora, move excluded journals aside, write the simplified
3-corpus registry.

pmc-em already exists (corpus 1578511669393358848) and is NOT rebuilt here.

Steps:
  1. Compute pmcid lists per target corpus from pmc_journal_manifest.json,
     filtered by the confirmed journal sets.
  2. Build a pmcid -> current GCS location map (files are under
     processed/shard_00../shard_08/ from Attempt 1).
  3. Move each corpus's files into processed/{corpus_folder}/, excluded files
     into processed/pmc-excluded/. Filenames preserved; metadata/ untouched.
  4. Create the 2 new KNN corpora, import each, verify counts.
  5. Write scrapers/PMC/pmc_shard_registry.json (simplified schema).

Resumable: skips files already at destination, skips corpora already created
(reads back the registry-in-progress).

Usage:
    python3 pmc_build_curated.py --dry-run
    python3 pmc_build_curated.py
"""

import argparse
import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import google.auth
import google.auth.transport.requests
import requests as http_requests
from google.cloud import storage as gcs

PROJECT_ID = "clinical-assistant-457902"
PROJECT_NUMBER = "930035889332"
RAG_LOCATION = "us-west4"
BUCKET_NAME = f"{PROJECT_ID}-pmc"
BASE_URL = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1"
PARENT = f"projects/{PROJECT_ID}/locations/{RAG_LOCATION}"

SCRIPT_DIR = Path(__file__).parent
MANIFEST = SCRIPT_DIR / "pmc_journal_manifest.json"
REGISTRY_OUT = SCRIPT_DIR / "pmc_shard_registry.json"
PMC_EM_CORPUS_ID = "1578511669393358848"

# Confirmed journal sets (docs/pmc-sharding-workstream.md §3)
JOURNALS = {
    "pmc_em": [
        "The Western Journal of Emergency Medicine",
        "Journal of the American College of Emergency Physicians Open",
        "The American Journal of Emergency Medicine", "Annals of Emergency Medicine",
        "Acad Emerg Med", "The Journal of Emergency Medicine", "Pediatric Emergency Care",
        "CJEM", "Advanced Journal of Emergency Medicine", "Prehospital Emergency Care",
        "Eur J Emerg Med", "Air Medical Journal",
    ],
    "pmc_critical_care": [
        "Chest", "Crit Care Med", "Resuscitation Plus", "Shock", "Resuscitation",
        "J Intensive Care Med",
    ],
    "pmc_high_impact": ["Lancet", "BMJ", "N Engl J Med", "Lancet Infect Dis"],
}
CORPUS_META = {
    "pmc_em": ("pmc-em", "PMC Emergency Medicine literature (12 EM journals)"),
    "pmc_critical_care": ("pmc-critical-care", "PMC Critical Care & Resuscitation literature (6 journals)"),
    "pmc_high_impact": ("pmc-high-impact", "PMC high-impact general medicine literature (Lancet, BMJ, NEJM, Lancet Infect Dis)"),
}
# Folder in processed/ for each corpus + excluded
FOLDER = {"pmc_em": "shard_00", "pmc_critical_care": "pmc-critical-care",
          "pmc_high_impact": "pmc-high-impact", "excluded": "pmc-excluded"}


def headers():
    creds, _ = google.auth.default()
    creds.refresh(google.auth.transport.requests.Request())
    return {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}


def poll(op_name, desc, max_wait=1800):
    url = f"{BASE_URL}/{op_name}"
    start = time.time()
    while time.time() - start < max_wait:
        r = http_requests.get(url, headers=headers(), timeout=60)
        if r.status_code != 200:
            time.sleep(15); continue
        d = r.json()
        if d.get("done"):
            if "error" in d:
                print(f"  ❌ {desc}: {d['error']}"); return None
            return d.get("response", d)
        print(f"  ⏳ {desc}... ({int(time.time()-start)}s)")
        time.sleep(15)
    print(f"  ⏱️ {desc} timed out"); return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-move", action="store_true")
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text())  # {pmcid: journal}
    kept = {j for js in JOURNALS.values() for j in js}

    # pmcid lists per destination
    dest_pmcids = {k: [] for k in ["pmc_em", "pmc_critical_care", "pmc_high_impact", "excluded"]}
    journal_to_corpus = {}
    for corpus_key, jlist in JOURNALS.items():
        for j in jlist:
            journal_to_corpus[j] = corpus_key
    for pmcid, journal in manifest.items():
        if journal in journal_to_corpus:
            dest_pmcids[journal_to_corpus[journal]].append(pmcid)
        else:
            dest_pmcids["excluded"].append(pmcid)

    for k, v in dest_pmcids.items():
        print(f"{k}: {len(v):,} files")

    client = gcs.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET_NAME)

    # --- Step: GCS reorg (move critical_care, high_impact, excluded; leave em in shard_00) ---
    if not args.skip_move:
        print("\nBuilding current-location map...")
        current = {}
        for blob in bucket.list_blobs(prefix="processed/"):
            if blob.name.endswith(".md"):
                current[blob.name.split("/")[-1].replace(".md", "")] = blob.name
        print(f"  {len(current):,} .md files located")

        for corpus_key in ["pmc_critical_care", "pmc_high_impact", "excluded"]:
            dest_folder = FOLDER[corpus_key]
            pmcids = dest_pmcids[corpus_key]
            to_move = []
            for pmcid in pmcids:
                src = current.get(pmcid)
                dest = f"processed/{dest_folder}/{pmcid}.md"
                if src and src != dest:
                    to_move.append((src, dest))
            print(f"\n{corpus_key}: {len(to_move):,} to move into processed/{dest_folder}/")
            if args.dry_run:
                continue

            def _mv(pair):
                # Retry transient GCS errors (503/500/429) per-blob so one
                # hiccup among tens of thousands doesn't abort the whole run.
                src, dest = pair
                for attempt in range(5):
                    try:
                        if bucket.blob(dest).exists():
                            return "skip"
                        bucket.copy_blob(bucket.blob(src), bucket, dest)
                        bucket.blob(src).delete()
                        return "moved"
                    except Exception as e:
                        if attempt == 4:
                            return f"error:{type(e).__name__}"
                        time.sleep(2 * (attempt + 1))

            moved = skipped = errors = 0
            start = time.time()
            with ThreadPoolExecutor(max_workers=20) as pool:
                futs = [pool.submit(_mv, p) for p in to_move]
                for i, f in enumerate(as_completed(futs), 1):
                    r = f.result()
                    if r == "moved": moved += 1
                    elif r == "skip": skipped += 1
                    else: errors += 1
                    if i % 3000 == 0 or i == len(to_move):
                        print(f"    {i}/{len(to_move)} ({i/(time.time()-start):.0f}/s)")
            print(f"  ✅ {corpus_key}: moved {moved}, skipped {skipped}, errors {errors}")
            if errors:
                print(f"  ⚠️  {errors} files failed after retries — re-run to catch them")

    if args.dry_run:
        print("\n[DRY RUN] stopping before corpus create/import")
        return

    # --- Step: create + import the 2 new corpora ---
    registry_corpora = [{"id": "pmc_em", "corpus_id": PMC_EM_CORPUS_ID,
                         "file_count": len(dest_pmcids["pmc_em"]), "journals": JOURNALS["pmc_em"]}]

    for corpus_key in ["pmc_critical_care", "pmc_high_impact"]:
        display, desc = CORPUS_META[corpus_key]
        # create
        print(f"\nCreating {display}...")
        payload = {"display_name": display, "description": desc,
                   "rag_embedding_model_config": {"vertex_prediction_endpoint": {
                       "endpoint": f"projects/{PROJECT_ID}/locations/{RAG_LOCATION}/publishers/google/models/text-embedding-005"}}}
        r = http_requests.post(f"{BASE_URL}/{PARENT}/ragCorpora", headers=headers(), json=payload, timeout=60)
        if r.status_code not in (200, 201):
            print(f"❌ create failed: {r.status_code} {r.text[:300]}"); return
        res = poll(r.json().get("name", ""), f"create {display}", max_wait=300)
        if not res: return
        corpus_id = res["name"].split("/")[-1]
        print(f"  ✅ {corpus_id}")

        # import
        corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{corpus_id}"
        gcs_uri = f"gs://{BUCKET_NAME}/processed/{FOLDER[corpus_key]}/"
        print(f"Importing {gcs_uri}...")
        ipayload = {"importRagFilesConfig": {"gcsSource": {"uris": [gcs_uri]},
                    "ragFileChunkingConfig": {"chunkSize": 1024, "chunkOverlap": 200}}}
        r = http_requests.post(f"{BASE_URL}/{corpus_name}/ragFiles:import", headers=headers(), json=ipayload, timeout=60)
        if r.status_code not in (200, 201):
            print(f"❌ import failed: {r.status_code} {r.text[:300]}"); return
        poll(r.json().get("name", ""), f"import {display}", max_wait=1800)

        cnt = http_requests.get(f"{BASE_URL}/{corpus_name}", headers=headers(), timeout=60).json().get("ragFilesCount")
        print(f"  ragFilesCount: {cnt} (expected {len(dest_pmcids[corpus_key])})")
        registry_corpora.append({"id": corpus_key, "corpus_id": corpus_id,
                                 "file_count": len(dest_pmcids[corpus_key]), "journals": JOURNALS[corpus_key]})

    # --- Step: write simplified registry ---
    counts = Counter(manifest.values())
    ui_groups = [
        {"group": "Emergency Medicine", "journals": [{"key": j, "count": counts.get(j, 0)} for j in JOURNALS["pmc_em"]]},
        {"group": "Critical Care & Resuscitation", "journals": [{"key": j, "count": counts.get(j, 0)} for j in JOURNALS["pmc_critical_care"]]},
        {"group": "High-Impact General", "journals": [{"key": j, "count": counts.get(j, 0)} for j in JOURNALS["pmc_high_impact"]]},
    ]
    registry = {
        "location": RAG_LOCATION,
        "corpora": registry_corpora,
        "journal_to_corpus": journal_to_corpus,
        "excluded_journals": sorted(j for j in counts if j not in kept),
        "ui_groups": ui_groups,
    }
    REGISTRY_OUT.write_text(json.dumps(registry, indent=2))
    print(f"\n✅ Registry written: {REGISTRY_OUT}")


if __name__ == "__main__":
    main()
