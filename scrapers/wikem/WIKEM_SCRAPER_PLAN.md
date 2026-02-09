# WikEM Scraper — Implementation Plan

## Overview
Scrape wikem.org (the Wikipedia of Emergency Medicine) to build a **general ED knowledge** RAG corpus that runs in parallel with department-specific local protocols.

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scraping method | `requests` + `BeautifulSoup4` | WikEM is server-rendered HTML, no JS needed |
| Storage | GCS bucket → Vertex AI RAG corpus | Same pipeline as local protocols |
| RAG corpus | **Separate** from local protocols | Keeps department data isolated; enables per-source toggle |
| Query strategy | Parallel queries to both corpora | Merge & interleave results with source labels |
| Update cadence | Monthly re-scrape | WikEM updates infrequently |
| Rate limiting | 1-2 req/sec with polite headers | Respect the site; avoid IP bans |

---

## Architecture

```
wikem.org
    │
    ▼
┌─────────────────────┐
│  wikem_scraper.py    │  Crawl topic pages, extract content
└─────────┬───────────┘
          │ JSON / Markdown files
          ▼
┌─────────────────────┐
│  GCS Bucket          │  gs://clinical-assistant-457902-wikem/
│  wikem-raw/          │    raw HTML snapshots
│  wikem-processed/    │    cleaned markdown + metadata
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Vertex AI RAG       │  Separate corpus: "wikem-general-ed"
│  (us-west4)          │  Indexed markdown chunks
└─────────────────────┘
```

---

## WikEM Page Structure

Each WikEM topic page (e.g., `wikem.org/wiki/Hyponatremia`) contains:

- **Title** — Topic name
- **Background** — Pathophysiology, epidemiology
- **Clinical Features** — Signs & symptoms
- **Differential Diagnosis** — DDx list
- **Evaluation / Workup** — Labs, imaging, assessment
- **Management** — Treatment algorithms, medications, disposition
- **Disposition** — Admit vs discharge criteria
- **See Also** — Related topics (useful for link crawling)
- **References** — Source citations

### Extraction Strategy
- Extract each **section** as a separate chunk with metadata
- Preserve section headers for retrieval context
- Keep internal links for crawl discovery
- Strip navigation, sidebars, footers, edit links

---

## Scraper Design

### Phase 1: Discovery (Sitemap / Category Crawl)
1. Hit `wikem.org/wiki/Special:AllPages` or sitemap.xml
2. Collect all topic page URLs
3. Filter out admin/meta pages (User:, Talk:, Template:, etc.)
4. Store URL list as `topic_urls.json`

### Phase 2: Content Extraction
For each topic URL:
1. `GET` the page with rate limiting (1 req/sec)
2. Parse with BeautifulSoup
3. Extract structured content:
   ```json
   {
     "url": "https://wikem.org/wiki/Hyponatremia",
     "title": "Hyponatremia",
     "last_scraped": "2026-02-08T00:00:00Z",
     "sections": [
       {
         "heading": "Background",
         "content": "Defined as serum sodium < 135 mEq/L...",
         "order": 1
       },
       {
         "heading": "Management",
         "content": "- Acute symptomatic: 3% saline...",
         "order": 5
       }
     ],
     "see_also": ["Hypernatremia", "SIADH", "Cerebral_salt_wasting"],
     "categories": ["Electrolyte", "Nephrology"]
   }
   ```
4. Save raw HTML to `wikem-raw/{topic_slug}.html`
5. Save cleaned JSON to `wikem-processed/{topic_slug}.json`
6. Convert to markdown for RAG indexing

### Phase 3: RAG Indexing
1. Create new Vertex AI RAG corpus: `wikem-general-ed`
2. Upload processed markdown files to corpus
3. Each chunk tagged with:
   - `source: "wikem"`
   - `topic: "Hyponatremia"`
   - `section: "Management"`
   - `url: "https://wikem.org/wiki/Hyponatremia"`

---

## File Structure

```
scrapers/
├── WIKEM_SCRAPER_PLAN.md          ← This file
├── wikem_scraper.py               ← Main scraper script
├── wikem_indexer.py               ← RAG corpus indexer
├── requirements.txt               ← requests, beautifulsoup4, lxml
├── topic_urls.json                ← Discovered topic URLs (generated)
└── tests/
    └── test_scraper.py            ← Test with single page
```

---

## GCS Storage Structure

```
gs://clinical-assistant-457902-wikem/
├── raw/                           ← Raw HTML snapshots
│   ├── hyponatremia.html
│   ├── stemi.html
│   └── ...
├── processed/                     ← Cleaned markdown
│   ├── hyponatremia.md
│   ├── stemi.md
│   └── ...
└── metadata/
    ├── topic_urls.json            ← All discovered URLs
    ├── scrape_log.json            ← Last scrape timestamps
    └── scrape_errors.json         ← Failed pages for retry
```

---

## Re-scrape Process

1. Load `scrape_log.json` to check last scrape date per topic
2. Only re-scrape pages older than 30 days
3. Compare new content hash vs stored hash — skip if unchanged
4. Re-index only changed documents in RAG corpus
5. Log results to `scrape_log.json`

---

## API Changes Required

### Multi-Source Query Flow
```python
# In rag_service.py — query both corpora in parallel
async def multi_source_query(query: str, sources: list[str]):
    tasks = []
    if "local" in sources:
        tasks.append(query_local_corpus(query))
    if "wikem" in sources:
        tasks.append(query_wikem_corpus(query))
    
    results = await asyncio.gather(*tasks)
    return merge_and_rank(results)
```

### Response Format Update
```json
{
  "answer": "For STEMI management...",
  "sources": [
    {
      "type": "local_protocol",
      "name": "STEMI Protocol v2.1",
      "org": "Demo Hospital",
      "confidence": 0.95
    },
    {
      "type": "wikem",
      "title": "STEMI",
      "url": "https://wikem.org/wiki/STEMI",
      "section": "Management",
      "confidence": 0.88
    }
  ],
  "images": [...]
}
```

---

## Frontend Changes Required

1. **Source toggle** — Checkbox or toggle in search UI:
   - ☑ Local Protocols
   - ☑ WikEM (General ED)
2. **Source badges** — Label each result chunk with its source
3. **Clickable citations** — WikEM results link back to wikem.org
4. **Source preference** — Remember user's toggle preference

---

## Cost Estimate

| Item | Estimate |
|------|----------|
| WikEM pages | ~5,000 topics |
| Avg page size | ~3 KB text |
| Total content | ~15 MB |
| GCS storage | < $0.01/month |
| RAG corpus | Included in Vertex AI pricing |
| Scrape time | ~2 hours at 1 req/sec |
| Monthly re-scrape | ~30 min (delta only) |

---

## MVP Success Criteria

1. ✅ Scrape at least 100 core ED topics (chest pain, trauma, toxicology, etc.)
2. ✅ Index into separate RAG corpus
3. ✅ Query returns relevant WikEM content with source attribution
4. ✅ Frontend shows source labels ("Local Protocol" vs "WikEM")
5. ✅ WikEM results include clickable link back to source page

---

## Phase Rollout

| Phase | Scope | Timeline |
|-------|-------|----------|
| **Phase 1** | Scrape 1 test page (Hyponatremia), verify extraction | Day 1 |
| **Phase 2** | Scrape top 100 ED topics, create RAG corpus | Day 2-3 |
| **Phase 3** | Multi-source API queries, merge results | Day 4-5 |
| **Phase 4** | Frontend source toggle + citations | Day 6-7 |
| **Phase 5** | Full scrape (~5,000 topics), monitoring | Week 2 |

---

## Robots.txt Check

Before scraping, verify `wikem.org/robots.txt` allows crawling of `/wiki/` pages.

## Legal / Attribution

- WikEM content is under **CC BY-SA 3.0** license
- Must provide attribution: "Content from WikEM (wikem.org) under CC BY-SA 3.0"
- Attribution will be displayed in the frontend alongside WikEM results

---

## ✅ Completed (Feb 8, 2026)

- [x] Phase 1 — Scraper built & tested on Hyponatremia
- [x] Phase 3 — Multi-source parallel API queries working
- [x] Phase 4 — Frontend source badges (Local blue / WikEM green), CC BY-SA attribution
- [x] Image pipeline — full-res images downloaded to GCS, metadata auto-uploaded
- [x] EM Universe / Protocol search mode toggle in frontend
- [x] 9 topics scraped & indexed: Hyponatremia, Arthrocentesis, Chest tube, Lumbar puncture, Balloon tamponade, Paracentesis, Pericardiocentesis, Thoracentesis, Transvenous pacing
- [x] Scrapers reorganized under `scrapers/wikem/`

---

## 🔜 TODO: Full WikEM Scrape (Feb 9)

### Goal
Scrape all ~5,000 WikEM topics and index them into the RAG corpus.

### Pre-scrape code changes needed

1. **Add batch/resume controls to `wikem_scraper.py`**
   - `--batch-size N` — scrape N topics then stop (default: all)
   - `--start-from <slug>` — resume from a specific topic alphabetically
   - Progress tracking in `output/metadata/scrape_progress.json` (last slug completed, count, timestamp)
   - Already skips existing by default (`--force` to re-scrape)

2. **Add skip-existing to `wikem_indexer.py`**
   - Track which files are already indexed in the RAG corpus
   - Compare content hashes — only re-import changed files
   - `--force` flag to re-index everything

3. **Add error retry logic**
   - `scrape_errors.json` already saved (built in)
   - Add `--retry-errors` flag to re-attempt only failed slugs
   - Add retry with backoff for transient network errors (503, timeout)

### Execution plan

| Step | Command | Time | Notes |
|------|---------|------|-------|
| 1. Discover all topics | `python3 wikem_scraper.py --discover` | ~2 min | Saves `topic_urls.json` |
| 2. Scrape all topics | `python3 wikem_scraper.py --all` | ~8-9 hours | 1.5s delay per page, skips existing |
| 3. Retry failures | `python3 wikem_scraper.py --retry-errors` | ~10 min | Re-attempt failed pages |
| 4. Index into RAG | `python3 wikem_indexer.py --index-all` | ~16-17 hours | ~12s per file (GCS upload + import) |

### Scale estimates

| Resource | Per Topic (avg) | × 5,000 topics | Cost |
|----------|----------------|-----------------|------|
| Scrape time | ~6s (1.5s delay + image download) | ~8-9 hours | Free |
| Images downloaded | ~2.7 per topic | ~13,500 images | — |
| GCS storage (images) | ~500KB | ~6.7 GB | ~$0.14/mo |
| GCS storage (markdown) | ~5KB | ~25 MB | negligible |
| RAG indexing time | ~12s per file | ~16-17 hours | Free tier |

### Option A: Run on laptop overnight
```bash
# Night 1: Discover + Scrape
python3 wikem_scraper.py --discover
python3 wikem_scraper.py --all                  # ~8hr, let it run overnight

# Night 2: Finish scrape if needed, then index
python3 wikem_scraper.py --all                  # picks up where it left off
python3 wikem_indexer.py --index-all            # ~17hr, run overnight
```

### Option B: Run on GCE VM (faster, unattended)
```bash
# Spin up e2-small in same project (auth is automatic via service account)
gcloud compute instances create wikem-scraper \
  --zone=us-west4-a --machine-type=e2-small \
  --scopes=cloud-platform

# SSH in, clone, run
gcloud compute ssh wikem-scraper
git clone https://github.com/derickjones/em-app-protocols.git
cd em-app-protocols/scrapers/wikem
pip install -r requirements.txt

# Run everything in a tmux session
tmux new -s scrape
python3 wikem_scraper.py --discover
python3 wikem_scraper.py --all        # ~8hr
python3 wikem_indexer.py --index-all  # ~17hr
# Detach with Ctrl+B, D — come back later

# Clean up when done
gcloud compute instances delete wikem-scraper --zone=us-west4-a
```

### Post-scrape: Incremental updates (ongoing)
- **Weekly cron** — re-run `--discover` to find new topics, scrape only new ones
- **Content hash comparison** — `content_hash` field in each JSON detects changed pages
- **Delta indexing** — only re-index files whose content hash changed since last import
