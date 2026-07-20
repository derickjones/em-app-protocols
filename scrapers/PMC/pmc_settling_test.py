#!/usr/bin/env python3
"""
Settling-time test for the curated PMC corpora (docs/pmc-sharding-workstream.md §2).

The one unexplained variable in the whole PMC speed investigation: corpora
created MONTHS ago (LITFL, WikEM, etc.) are fast (~0.6-1.5s); corpora created
TODAY (the 9 shards, then pmc-em, then the curated 3) are slow (10-30s),
regardless of size or count. Waits of 2h and 4h showed no improvement. This
tests a much longer window.

Run this manually whenever (e.g. next day, 12-24h+ after the ~2026-07-19 evening
build). It prints elapsed-since-build context and times each curated corpus
isolated, so results are directly comparable to the ~16-30s baseline captured
at build time.

    python3 pmc_settling_test.py
"""

import json
import time
from datetime import datetime, timezone

import requests
import google.auth
import google.auth.transport.requests

RAG_LOCATION = "us-west4"
PROJECT_NUMBER = "930035889332"
BASE_URL = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1"

# Curated corpora built ~2026-07-19 evening (build-time isolated baseline: 16-30s each)
CORPORA = {
    "pmc_em": "1578511669393358848",
    "pmc_critical_care": "8496040697034440704",
    "pmc_high_impact": "3307893926303629312",
}
# A months-old corpus as the fast control (created 2026-02, ~0.6-1.5s)
CONTROL_LITFL = "7991637538768945152"


def headers():
    creds, _ = google.auth.default()
    creds.refresh(google.auth.transport.requests.Request())
    return {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}


def time_corpus(label, corpus_id, runs=4):
    corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{corpus_id}"
    url = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}:retrieveContexts"
    payload = {"query": {"text": "tPA stroke dosing contraindications", "similarityTopK": 5},
               "vertex_rag_store": {"rag_corpora": [corpus_name]}}
    times = []
    for i in range(runs):
        t0 = time.time()
        try:
            r = requests.post(url, headers=headers(), json=payload, timeout=60)
            e = time.time() - t0
            times.append(e)
            print(f"  [{label}] run {i+1}: {e:.2f}s (status {r.status_code})")
        except Exception as ex:
            e = time.time() - t0
            print(f"  [{label}] run {i+1}: ERROR after {e:.2f}s — {type(ex).__name__}")
    if times:
        print(f"  [{label}] avg {sum(times)/len(times):.2f}s, min {min(times):.2f}s")
    return times


print(f"=== PMC settling test @ {datetime.now(timezone.utc).isoformat()} ===")
print("Build-time baseline (isolated): pmc-em ~10-16s, critical-care/high-impact ~24-30s")
print("Fast control (LITFL, months old): expect ~0.6-1.5s\n")

print("--- Fast control ---")
time_corpus("litfl (control)", CONTROL_LITFL)
print("\n--- Curated corpora ---")
for label, cid in CORPORA.items():
    time_corpus(label, cid)

print("\nInterpretation:")
print("  If curated corpora now ~1-2s (near control): SETTLING confirmed — deploy is worth it.")
print("  If still 10-30s while control stays ~1s: settling ruled out even at this window;")
print("    speed is not fixable by corpus sizing — decide between curated-anyway / Pinecone / tier.")
