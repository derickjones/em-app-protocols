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
