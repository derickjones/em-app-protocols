# WikEM Corpus: Scrape, Upload & Re-Index Guide

> **Last updated:** February 2026
> **Frequency:** Every ~6 months or as needed
> **Time required:** ~20 minutes total (mostly automated)

---

## Overview

The WikEM corpus provides general emergency medicine knowledge from [wikem.org](https://wikem.org) (~1,900 clinical topics). It powers the **Globe 🌐** search source in the app.

The pipeline has 3 stages:

```
1. SCRAPE  →  2. UPLOAD  →  3. INDEX
wikem.org      GCS bucket    Vertex AI RAG corpus
(~12 min)      (~18 sec)     (~3 min)
```

### What lives where

| Asset | Location |
|-------|----------|
| Raw HTML | `scrapers/wikem/output/raw/` (local) |
| Processed .md + .json | `scrapers/wikem/output/processed/` (local) |
| Images | `gs://clinical-assistant-457902-wikem/images/{slug}/` |
| Metadata JSON | `gs://clinical-assistant-457902-wikem/metadata/{slug}.json` |
| Processed .md (GCS) | `gs://clinical-assistant-457902-wikem/processed/{slug}.md` |
| RAG corpus config | `scrapers/wikem/wikem_rag_config.json` |
| Cloud Run env var | `WIKEM_CORPUS_ID` on `em-protocol-api` |

---

## Prerequisites

```bash
# From the repo root
cd scrapers/wikem

# Make sure you're authenticated with GCP
gcloud auth application-default login

# Install dependencies (if first time)
pip install -r requirements.txt
```

---

## Full Re-Scrape + Re-Index (recommended every 6 months)

### Step 1: Scrape all of WikEM

```bash
cd scrapers/wikem
python3 wikem_bulk_scrape.py --workers 20 --force
```

| Flag | Purpose |
|------|---------|
| `--workers 20` | Parallel threads (20 is a good balance) |
| `--force` | Re-scrape even if files already exist locally |
| `--limit N` | Only scrape N pages (useful for testing) |
| `--resume` | Skip pages that already have local output |
| `--retry-errors` | Only retry pages that failed last time |

**What it does:**
- Reads the discovery data (`discovery/wikem_discovery.json`) for the list of pages
- Scrapes each page (HTML → sections, images, categories)
- Downloads images to GCS (`images/{slug}/`)
- Uploads metadata to GCS (`metadata/{slug}.json`)
- Saves processed `.md` and `.json` files locally

**Expected output:**
```
✅ 1,898 pages scraped in ~12 minutes
32 "errors" (index/navigation pages with no clinical content — expected)
```

**Check errors if needed:**
```bash
cat output/metadata/bulk_scrape_errors.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'Errors: {len(data)}')
for e in data:
    print(f'  {e[\"slug\"]}: {e[\"error\"][:80]}')
"
```

### Step 2: Upload to GCS + Re-Index into Vertex AI RAG

```bash
python3 wikem_reindex.py
```

**What it does (all automated):**
1. Uploads all 1,899 `.md` files to `gs://clinical-assistant-457902-wikem/processed/`
2. Deletes the old RAG corpus
3. Creates a new RAG corpus with `text-embedding-005`
4. Batch imports all files from GCS into the new corpus
5. Saves the new corpus ID to `wikem_rag_config.json`

**Expected output:**
```
STEP 1/4: GCS upload — 1,899 files in ~18s
STEP 2/4: Delete old corpus — ~5s
STEP 3/4: Create new corpus — ~10s
STEP 4/4: Batch import — ~3 min

RE-INDEX COMPLETE
  Corpus ID: <new_id>
```

### Step 3: Update Cloud Run (only if corpus ID changed)

The script will tell you if the corpus ID changed. If it did:

```bash
gcloud run services update em-protocol-api \
  --region us-central1 \
  --update-env-vars WIKEM_CORPUS_ID=<new_corpus_id>
```

Or set `WIKEM_CORPUS_ID` in the [Cloud Console](https://console.cloud.google.com/run/detail/us-central1/em-protocol-api/revisions?project=clinical-assistant-457902) under Environment Variables.

---

## Partial Operations

### Upload to GCS only (no corpus rebuild)

```bash
python3 wikem_reindex.py --upload-only
```

Useful if you just want to refresh the `.md` files in GCS without rebuilding the RAG corpus.

### Rebuild corpus from existing GCS files (skip upload)

```bash
python3 wikem_reindex.py --skip-upload
```

Useful if the `.md` files in GCS are already up to date and you just need to recreate the corpus (e.g., after accidentally deleting it).

### Dry run (preview without changes)

```bash
python3 wikem_reindex.py --dry-run
```

Shows what would happen without making any changes.

### Test scrape (small batch)

```bash
python3 wikem_bulk_scrape.py --workers 5 --limit 10
```

Scrapes just 10 pages to verify everything works.

---

## Architecture Reference

```
scrapers/wikem/
├── wikem_discovery.py      # Discovers all WikEM page URLs from sitemap
├── wikem_scraper.py        # Core scraping logic (per-page extraction)
├── wikem_bulk_scrape.py    # Parallel bulk scraper (orchestrates wikem_scraper)
├── wikem_reindex.py        # GCS upload + RAG corpus rebuild
├── wikem_indexer.py         # Legacy single-file indexer (superseded by wikem_reindex.py)
├── wikem_rag_config.json   # Saved corpus ID & config
├── discovery/
│   └── wikem_discovery.json    # Cached list of all WikEM URLs
└── output/
    ├── raw/                # Raw HTML from wikem.org
    ├── processed/          # .md and .json per topic
    └── metadata/           # Bulk scrape logs & error reports
```

### Key Config Values

| Config | Value | Where |
|--------|-------|-------|
| GCP Project | `clinical-assistant-457902` | All scripts |
| Project Number | `930035889332` | All scripts |
| RAG Region | `us-west4` | wikem_reindex.py |
| GCS Bucket | `clinical-assistant-457902-wikem` | All scripts |
| Embedding Model | `text-embedding-005` | wikem_reindex.py |
| Chunk Size | 1024 tokens | wikem_reindex.py |
| Chunk Overlap | 200 tokens | wikem_reindex.py |

### How the API uses it

- `api/rag_service.py` reads `WIKEM_CORPUS_ID` env var
- When user has Globe 🌐 active, queries go to the WikEM corpus
- Image metadata is fetched from `gs://clinical-assistant-457902-wikem/metadata/{slug}.json`
- Images are served from `gs://clinical-assistant-457902-wikem/images/{slug}/{filename}`

---

## Troubleshooting

### "No discovery data found"
Run the discovery script first:
```bash
python3 wikem_discovery.py
```

### Scrape errors on specific pages
Most "errors" are index/navigation pages that don't have clinical content. Check `output/metadata/bulk_scrape_errors.json` — if they're all pages like "Search", "WikEM_Awards", "Main_Page_Test_Example", that's normal.

To retry only failed pages:
```bash
python3 wikem_bulk_scrape.py --workers 20 --retry-errors
```

### Import operation timed out
The reindex script has a 30-minute timeout for the import operation. If it times out, the import may still be running server-side. Check the operation status in GCP Console under Vertex AI > RAG Corpora, or re-run:
```bash
python3 wikem_reindex.py --skip-upload
```

### WikEM queries returning no results after re-index
Make sure you updated the Cloud Run env var:
```bash
gcloud run services describe em-protocol-api --region us-central1 --format="value(spec.template.spec.containers[0].env)"
```
Verify `WIKEM_CORPUS_ID` matches the value in `wikem_rag_config.json`.

### Connection pool warnings
The `Connection pool is full, discarding connection` warnings during upload are harmless — they come from the parallel upload threads sharing HTTP connections. No action needed.
