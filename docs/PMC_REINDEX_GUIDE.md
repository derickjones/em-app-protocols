# PMC Corpus: Scrape, Upload & Re-Index Guide

> **Last updated:** April 2026
> **Frequency:** Every ~6 months or as needed
> **Time required:** ~3 hours total (mostly automated)

---

## Overview

The PMC corpus provides peer-reviewed medical literature from [PubMed Central](https://www.ncbi.nlm.nih.gov/pmc/) (~56,000 articles from 37 journals, 2015–present). It powers the **Globe 🌐** search source alongside WikEM, LITFL, REBEL EM, and ALiEM.

The pipeline has 3 stages:

```
1. DISCOVER  →  2. SCRAPE  →  3. INDEX
PubMed API       PMC OA API    Vertex AI RAG corpus
(~3 min)         (~2.5 hrs)    (~15 min)
```

### What lives where

| Asset | Location |
|-------|----------|
| Discovery cache | `scrapers/PMC/discovery/pmc_discovery.json` (local, gitignored) |
| Processed .md | `scrapers/PMC/output/processed/` (local) + `gs://clinical-assistant-457902-pmc/processed/` |
| Metadata JSON | `scrapers/PMC/output/processed/` (local) + `gs://clinical-assistant-457902-pmc/metadata/` |
| Article images | `gs://clinical-assistant-457902-pmc/images/{PMCID}/` |
| RAG corpus config | `scrapers/PMC/pmc_rag_config.json` |
| Cloud Run env var | `PMC_CORPUS_ID` hardcoded default in `api/rag_service.py` |

### Journals covered (37 journals, 4 categories)

**Emergency Medicine (12):** Annals of Emergency Medicine, Academic Emergency Medicine, JACEP Open, American Journal of Emergency Medicine, Journal of Emergency Medicine, Western Journal of Emergency Medicine, Pediatric Emergency Care, CJEM, Advanced Journal of Emergency Medicine, Prehospital Emergency Care, European Journal of Emergency Medicine, Air Medical Journal

**Critical Care & Resuscitation (7):** AJRCCM, CHEST, Critical Care Medicine, Resuscitation, Resuscitation Plus, Shock, Journal of Intensive Care Medicine

**JAMA Family (10):** JAMA, JAMA Network Open, JAMA Internal Medicine, JAMA Surgery, JAMA Neurology, JAMA Pediatrics, JAMA Cardiology, JAMA Oncology, JAMA Ophthalmology, JAMA Otolaryngology

**High-Impact General (8):** NEJM, The Lancet, Lancet Infectious Diseases, Lancet Respiratory Medicine, Lancet Neurology, BMJ, Annals of Internal Medicine, Mayo Clinic Proceedings

---

## Prerequisites

```bash
cd scrapers/PMC

# GCP auth
gcloud auth application-default login

# NCBI API credentials (required for discovery + scrape)
export ENTREZ_EMAIL="derickdavidjones@gmail.com"
export ENTREZ_API_KEY="2b27b5be1554634562c7c2d421cf8d127208"

# Install deps (first time only)
pip install -r requirements.txt
```

---

## Full Re-Scrape + Re-Index

### Step 1: Discover articles

```bash
python3 pmc_discovery.py --force
```

Queries PubMed for all EM journal articles (2015–present). Saves article list to `discovery/pmc_discovery.json`.

### Step 2: Scrape all articles

```bash
python3 pmc_bulk_scrape.py --workers 20 --force
```

| Flag | Purpose |
|------|---------|
| `--workers 20` | Parallel threads |
| `--force` | Re-scrape everything |
| `--limit N` | Scrape only N articles (testing) |
| `--resume` | Skip already-scraped articles |
| `--retry-errors` | Only retry previously failed articles |

**What it does:**
- Fetches full text via PMC OA API (falls back to abstract-only)
- Downloads article figures to GCS
- Saves `.md` (content) and `.json` (metadata) locally

**Expected:** ~56,000 articles in ~2.5 hrs with 20 workers, ~66% full-text, ~34% abstract-only

### Step 3: Re-index into Vertex AI

```bash
python3 pmc_reindex.py
```

| Flag | Purpose |
|------|---------|
| `--upload-only` | Upload to GCS only, don't rebuild corpus |
| `--skip-upload` | Rebuild corpus from existing GCS files |
| `--dry-run` | Show what would happen |

**What it does:**
1. Uploads all `.md` files to GCS
2. Deletes old RAG corpus
3. Creates new corpus with `text-embedding-005`
4. Batch-imports all files from GCS
5. Updates `pmc_rag_config.json` with new corpus ID

**Expected:** ~15 min for the full rebuild (56K files)

### Step 4: Update Cloud Run / API defaults

The corpus ID is hardcoded as the default in `api/rag_service.py`. After re-indexing, either:

1. **Update the hardcoded default** in `api/rag_service.py` and redeploy:
   ```python
   PMC_CORPUS_ID = os.environ.get("PMC_CORPUS_ID", "<NEW_CORPUS_ID>")
   ```

2. **Or set it as a Cloud Run env var** (overrides the default):
   ```bash
   gcloud run services update em-protocol-api \
     --region us-central1 \
     --project clinical-assistant-457902 \
     --set-env-vars "PMC_CORPUS_ID=<NEW_CORPUS_ID>"
   ```

---

## Quick Reference

```bash
# Full rebuild (all 3 steps)
cd scrapers/PMC
export ENTREZ_EMAIL="derickdavidjones@gmail.com"
export ENTREZ_API_KEY="2b27b5be1554634562c7c2d421cf8d127208"
python3 pmc_discovery.py --force
python3 pmc_bulk_scrape.py --workers 20 --force
python3 pmc_reindex.py

# Then update Cloud Run with the new corpus ID from the output
```

## Current Corpus

- **Corpus ID:** `6838716034162098176` ⚠️ **STALE — still indexes the old 6,598-article EM-only corpus**
- **Articles indexed:** 6,598 (from Feb 2026 build)
- **Articles scraped locally:** 56,158 (from Apr 2026 scrape — **needs re-index**)
- **GCS bucket:** `gs://clinical-assistant-457902-pmc/`
- **GCS processed/:** 6,604 files ⚠️ **needs upload of ~50K new .md files**
- **GCS metadata/:** 56,156 files ✅ (already uploaded during scrape)
- **RAG location:** `us-west4`
- **Embedding model:** `text-embedding-005`
- **Cloud Run service:** `em-protocol-api` in `us-central1`
