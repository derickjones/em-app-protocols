# PMC Corpus: Scrape, Upload & Re-Index Guide

> **Last updated:** February 2026
> **Frequency:** Every ~6 months or as needed
> **Time required:** ~45 minutes total (mostly automated)

---

## Overview

The PMC corpus provides peer-reviewed emergency medicine literature from [PubMed Central](https://www.ncbi.nlm.nih.gov/pmc/) (~6,600 articles from 11 EM journals, 2015–present). It powers the **Globe 🌐** search source alongside WikEM.

The pipeline has 3 stages:

```
1. DISCOVER  →  2. SCRAPE  →  3. INDEX
PubMed API       PMC OA API    Vertex AI RAG corpus
(~2 min)         (~33 min)     (~8 min)
```

### What lives where

| Asset | Location |
|-------|----------|
| Discovery cache | `scrapers/PMC/discovery/pmc_discovery.json` (local, gitignored) |
| Processed .md | `scrapers/PMC/output/processed/` (local) + `gs://clinical-assistant-457902-pmc/processed/` |
| Metadata JSON | `scrapers/PMC/output/processed/` (local) + `gs://clinical-assistant-457902-pmc/metadata/` |
| Article images | `gs://clinical-assistant-457902-pmc/images/{PMCID}/` |
| RAG corpus config | `scrapers/PMC/pmc_rag_config.json` |
| Cloud Run env var | `PMC_CORPUS_ID` on `em-api` |

### Journals covered

Annals of Emergency Medicine, Academic Emergency Medicine, Journal of Emergency Medicine, Emergency Medicine Journal, American Journal of Emergency Medicine, Western Journal of Emergency Medicine, CJEM, Emergency Medicine Australasia, European Journal of Emergency Medicine, World Journal of Emergency Medicine, International Journal of Emergency Medicine

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

**Expected:** ~6,600 articles in ~33 min, ~94% full-text, ~6% abstract-only

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

**Expected:** ~8 min for the full rebuild

### Step 4: Update Cloud Run

The reindex script prints the command, but it's:

```bash
gcloud run services update em-api \
  --region us-west1 \
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

- **Corpus ID:** `6838716034162098176`
- **Articles:** 6,604
- **GCS bucket:** `gs://clinical-assistant-457902-pmc/`
- **Embedding model:** `text-embedding-005`
- **Cost:** ~$2.63 one-time embedding, ~$0.69–2.31/month ongoing
