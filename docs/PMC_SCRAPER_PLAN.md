# PMC Scraper System — Implementation Plan

> **Status:** PLANNING (awaiting approval before coding)
> **Location:** `scrapers/PMC/`
> **Reindex frequency:** Every ~6 months

---

## 1. Overview

Build a PubMed Central (PMC) scraper system that:
- Scrapes EM journal articles (2015–present) from NCBI's BioC API
- Extracts full text + images for full-text articles, abstract-only for others
- Uploads to a dedicated GCS bucket and Vertex AI RAG corpus
- Integrates into the app as a third source alongside WikEM and local protocols
- Displays academic-style citations with clickable PMC/PubMed links

---

## 2. Journal List (11 journals)

| # | Journal |
|---|---------|
| 1 | Annals of Emergency Medicine |
| 2 | Academic Emergency Medicine |
| 3 | Journal of the American College of Emergency Physicians Open |
| 4 | The American Journal of Emergency Medicine |
| 5 | The Journal of Emergency Medicine |
| 6 | The Western Journal of Emergency Medicine |
| 7 | Advanced Journal of Emergency Medicine |
| 8 | European Journal of Emergency Medicine |
| 9 | Prehospital Emergency Care |
| 10 | Air Medical Journal |
| 11 | Pediatric Emergency Care |

---

## 3. Pipeline Architecture

```
scrapers/PMC/
├── pmc_discovery.py        # Fetch all PMCIDs from 11 journals (2015–present) via Entrez
├── pmc_scraper.py          # Core per-article scraping (BioC full-text + abstract fallback)
├── pmc_bulk_scrape.py      # Parallel bulk scraper (10 workers, rate-limited)
├── pmc_reindex.py          # Upload .md to GCS + rebuild Vertex AI RAG corpus
├── pmc_rag_config.json     # Saved corpus ID & config
├── requirements.txt
├── discovery/
│   └── pmc_discovery.json  # Cached list of {PMCID, journal, year} — deduplicated
└── output/
    ├── raw/                # Raw JSON responses from BioC API
    ├── processed/          # .md and .json per article
    └── metadata/           # Scrape logs, error reports, summary stats
```

### Step-by-step flow

```
1. DISCOVER     →  2. SCRAPE        →  3. REINDEX       →  4. DEPLOY
Entrez API         BioC API            GCS + Vertex AI     Cloud Run env var
(~2 min)           (~30-60 min)        (~5-10 min)         (~30 sec)
```

---

## 4. Discovery (`pmc_discovery.py`)

- Uses NCBI Entrez `esearch` to find all PMCIDs per journal
- Filters: `2015/01/01:3000[PDAT]` (2015 to present)
- Deduplicates by PMCID across all journals (some articles indexed in multiple journals)
- Saves to `discovery/pmc_discovery.json`:
  ```json
  {
    "discovered_at": "2026-02-11T...",
    "total_unique": 45000,
    "by_journal": {
      "Annals of Emergency Medicine": 8500,
      ...
    },
    "articles": [
      {"pmcid": "PMC12345678", "journal": "Annals of Emergency Medicine"},
      ...
    ]
  }
  ```
- **Env vars needed:** `ENTREZ_EMAIL`, `ENTREZ_API_KEY`
- Without API key: 3 req/sec. With key: 10 req/sec.

---

## 5. Scraping (`pmc_scraper.py` + `pmc_bulk_scrape.py`)

### Per-article logic (`pmc_scraper.py`)

1. **Try BioC full-text API:**
   `https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json/{PMCID}/unicode`
   - If `Content-Type: application/json` → full article available
   - Parse sections (title, abstract, intro, methods, results, discussion, etc.)
   - Extract figure references for image download

2. **Fallback to BioC abstract API:**
   `https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pubmed.cgi/BioC_json/{PMID}/unicode`
   - Parse title + abstract only
   - No image extraction for abstract-only

3. **Image extraction (full-text articles only):**
   - Fetch PMC HTML page: `https://pmc.ncbi.nlm.nih.gov/articles/{PMCID}/`
   - Parse `<img>` tags for figures (skip icons/logos)
   - Download images → upload to `gs://clinical-assistant-457902-pmc/images/{PMCID}/`
   - Upload metadata → `gs://clinical-assistant-457902-pmc/metadata/{PMCID}.json`

4. **Output per article:**

   **Markdown (`output/processed/{PMCID}.md`):**
   ```markdown
   # Article Title Here

   **Journal:** Annals of Emergency Medicine
   **Authors:** Smith J, Doe A, et al.
   **Year:** 2023
   **PMCID:** PMC12345678
   **URL:** https://pmc.ncbi.nlm.nih.gov/articles/PMC12345678/
   **Type:** full_text

   ## Abstract
   ...

   ## Introduction
   ...

   ## Methods
   ...

   ## Results
   ...

   ## Discussion
   ...

   ## Conclusions
   ...
   ```

   **JSON (`output/processed/{PMCID}.json`):**
   ```json
   {
     "pmcid": "PMC12345678",
     "title": "Article Title",
     "journal": "Annals of Emergency Medicine",
     "authors": "Smith J, Doe A, et al.",
     "year": "2023",
     "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12345678/",
     "type": "full_text",
     "sections": [...],
     "images": [{"url": "gs://...", "alt": "Figure 1. ..."}]
   }
   ```

### Bulk scraper (`pmc_bulk_scrape.py`)

- **10 workers** (ThreadPoolExecutor)
- **0.15s delay** between requests per worker (~66 req/sec total, well within 10/sec Entrez limit since BioC is separate)
- Progress tracking with rate, ETA, success/skip/error counts
- Tracks `full_text` vs `abstract_only` counts
- `--workers`, `--limit`, `--force`, `--resume`, `--retry-errors` flags (same as WikEM)

### Summary stats (`output/metadata/bulk_scrape_log.json`)
```json
{
  "total_articles": 45000,
  "scraped": 44500,
  "full_text": 28000,
  "abstract_only": 16500,
  "full_text_pct": "62.9%",
  "errors": 500,
  "images_downloaded": 85000,
  "time_minutes": 45,
  "by_journal": {
    "Annals of Emergency Medicine": {"total": 8500, "full_text": 5200, "abstract": 3300},
    ...
  }
}
```

---

## 6. Re-Index (`pmc_reindex.py`)

Identical pattern to `wikem_reindex.py`:

1. Upload all `.md` files to `gs://clinical-assistant-457902-pmc/processed/`
2. Delete old PMC RAG corpus
3. Create new PMC RAG corpus (`pmc-em-literature`, `text-embedding-005`)
4. Batch import from GCS
5. Save new corpus ID to `pmc_rag_config.json`
6. Print `gcloud` command to update Cloud Run env var

**GCS bucket:** `clinical-assistant-457902-pmc` (region: `us-west4`, same as RAG corpus)

**Chunk config:** 1024 tokens, 200 overlap (same as WikEM)

---

## 7. API Integration (`rag_service.py`)

### New env var
```
PMC_CORPUS_ID=<corpus_id>
```

### Changes to `rag_service.py`

Add third corpus alongside local + WikEM:

```python
PMC_CORPUS_ID = os.environ.get("PMC_CORPUS_ID", "")
PMC_BUCKET = f"{PROJECT_ID}-pmc"
```

In `_retrieve_multi_source()`, add `"pmc"` source:
```python
def fetch_pmc():
    contexts = self._retrieve_contexts(query, self.pmc_corpus_name)
    for ctx in contexts:
        ctx["source_type"] = "pmc"
    return contexts
```

All 3 corpora queried in parallel (ThreadPoolExecutor already supports this).

Add `_get_pmc_metadata()` for image retrieval (same pattern as `_get_wikem_metadata()`).

### Citation format in API response

```json
{
  "source_type": "pmc",
  "protocol_id": "PMC12345678",
  "source_uri": "gs://clinical-assistant-457902-pmc/processed/PMC12345678.md",
  "title": "Emergency Management of Hyponatremia in the ED",
  "journal": "Annals of Emergency Medicine",
  "authors": "Smith J, Doe A, et al.",
  "year": "2023",
  "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12345678/"
}
```

---

## 8. Frontend Integration (`page.tsx`)

### Globe 🌐 button behavior
- Currently Globe toggles `"wikem"` in sources
- **Change:** Globe toggles BOTH `"wikem"` and `"pmc"` together
- Globe = "EM Universe" = WikEM + PMC literature

### Citation display for PMC results

**Current WikEM citation:**
```
🌐 Hyponatremia — wikem.org
```

**New PMC citation (academic style):**
```
📚 Smith J, Doe A, et al. "Emergency Management of Hyponatremia in the ED."
   Annals of Emergency Medicine, 2023.  [PMC]  🔗
```

- `📚` or `PMC` badge to distinguish from WikEM `🌐`
- Title in quotes, journal in italics, year
- Clickable link to PMC article
- Authors truncated with "et al." if > 3

### Images
- PMC images displayed in the same image carousel as WikEM/local images
- Source label: "PMC: Article Title"

---

## 9. File Changes Summary

| File | Change |
|------|--------|
| `scrapers/PMC/` | **NEW** — entire scraper system (5 scripts) |
| `api/rag_service.py` | Add PMC corpus, `fetch_pmc()`, `_get_pmc_metadata()` |
| `api/main.py` | Add PMC citation formatting in `/query` response |
| `frontend/app/page.tsx` | Globe toggles wikem+pmc, PMC citation display |
| `docs/PMC_REINDEX_GUIDE.md` | **NEW** — reindex documentation |

---

## 10. Build Order

1. **Phase 1 — Scraper scripts** (no app changes)
   - `pmc_discovery.py` → run discovery, confirm article counts
   - `pmc_scraper.py` → test on 5 articles
   - `pmc_bulk_scrape.py` → full scrape
   - `pmc_reindex.py` → upload + create corpus

2. **Phase 2 — API integration**
   - Add PMC corpus to `rag_service.py`
   - Add PMC citation formatting to `main.py`
   - Deploy Cloud Run with `PMC_CORPUS_ID`

3. **Phase 3 — Frontend**
   - Globe button toggles wikem + pmc
   - PMC citation badge + academic format
   - Deploy to Vercel

---

## 11. Open Items

- [ ] User needs to create NCBI API key at https://www.ncbi.nlm.nih.gov/account/settings/
- [ ] Create GCS bucket `clinical-assistant-457902-pmc` in `us-west4`
- [ ] Estimate total article count after discovery (expect 30K-60K for 2015-present across 11 journals)
- [ ] Vertex AI RAG corpus file limits — may need to verify the corpus can handle 30K+ files

---

**Ready to proceed?** Get your NCBI API key, and I'll start building Phase 1.
