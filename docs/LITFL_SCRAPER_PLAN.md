# LITFL (Life in the Fast Lane) Scraper — Integration Plan

> **Created:** February 2026  
> **Status:** Planning  
> **Modeled after:** WikEM scraper pipeline

---

## Overview

Scrape [litfl.com](https://litfl.com) (Life in the Fast Lane) — a premier FOAMed (Free Open-Access Medical education) resource for emergency medicine, critical care, toxicology, ECG interpretation, and more — to build a dedicated RAG corpus alongside WikEM and PMC.

### Why LITFL?

| Feature | WikEM | LITFL | Complementary Value |
|---------|-------|-------|---------------------|
| Content style | Wiki reference (concise) | Deep-dive articles (detailed) | LITFL fills in pharmacology, evidence, clinical nuance |
| Pharmacology | Brief drug mentions | Full CCC drug monographs (dose, PK, evidence) | Massive pharmacology depth |
| ECG | None | 100+ ECG cases with images | Unique ECG interpretation capability |
| Evidence/Trials | Sparse references | Detailed trial summaries & critique | Evidence-based medicine layer |
| Critical Care | Limited | Full Critical Care Compendium (CCC) | ICU-level detail |
| Toxicology | Basic | Comprehensive toxicology library | Detailed antidote/management |
| Imaging | None | Top 100 CT, Top 100 CXR | Radiology case library |
| Eponyms | None | Eponymictionary (1000+ entries) | Medical history & terminology |

---

## License & Attribution

### License

**Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**

Found in the footer of every LITFL page:
> *#FOAMed Medical Education Resources by LITFL is licensed under a Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License. Based on a work at https://litfl.com*

The ECG Library page specifically states:
> *All our ECGs are free to reproduce for educational purposes, provided:*  
> *• The image is credited to litfl.com.*  
> *• The teaching activity is on a not-for-profit basis.*  
> *• The image is not otherwise labelled as belonging to a third-party.*

### What CC BY-NC-SA 4.0 Requires

| Requirement | How We Comply |
|-------------|---------------|
| **Attribution (BY)** | Every `.md` file includes `Source: [LITFL](url) (CC BY-NC-SA 4.0)` with author names |
| **NonCommercial (NC)** | App is a non-commercial educational/clinical tool |
| **ShareAlike (SA)** | Derived content retains the same CC BY-NC-SA 4.0 license |
| **No additional restrictions** | No DRM or additional terms applied |

### Attribution in the App

- Every RAG-generated answer citing LITFL content will show "LITFL" as the source type in citations
- Citation links will point back to the original LITFL URL
- Author names will be preserved in metadata
- The Gemini prompt will include `(LITFL - CC BY-NC-SA 4.0)` labels on LITFL context chunks

### robots.txt Compliance

LITFL's `robots.txt` is permissive:
```
User-agent: *
Disallow: /wp-admin/
Sitemap: https://litfl.com/sitemap_index.xml
```

Only `/wp-admin/` is disallowed — all content pages are allowed for crawling.

---

## Scale Analysis

### Content Volume

| Sitemap | URL Count |
|---------|-----------|
| post-sitemap.xml | 1,001 |
| post-sitemap2.xml | 1,000 |
| post-sitemap3.xml | 999 |
| post-sitemap4.xml | 1,000 |
| post-sitemap5.xml | 1,000 |
| post-sitemap6.xml | 1,000 |
| post-sitemap7.xml | 1,000 |
| post-sitemap8.xml | 317 |
| **Total posts** | **~7,317** |

Additionally: `page-sitemap.xml` (static pages), `category-sitemap.xml` (category index pages — skip these).

### Content Categories (from category-sitemap.xml)

Major clinical categories:
- **CCC** (Critical Care Compendium) — pharmacology, airway, acid-base, clinical governance
- **ECG Library** — basics, diagnosis, cases
- **Toxicology Library** — antidotes, antivenoms
- **Medical Specialties** — cardiology, neurology, pulmonology, nephrology, anesthesiology, burns, radiology, general surgery, cardiothoracic surgery, urology, vascular surgery, adventure medicine
- **Clinical Cases** — ECG exigency, cardiovascular curveball
- **Eponym/Eponymictionary** — medical eponyms and history
- **Top 100** — ECG, CT scans, CXR, airway cases
- **Basic Science** — anatomy, chemistry, pharmacology, physiology
- **Examinations** — ACEM fellowship, CICM fellowship
- **Procedures** — clinical procedures
- **COVID** — COVID-related content
- **Clinical Research** — EBM, research methodology

Non-clinical categories (may want to skip or deprioritize):
- Blog news, book reviews, app reviews, conference reports
- Literary medicine, podcasts, administration
- 3D printing, SMACC conference talks

### Estimated Scrape Time

With ~7,300 pages at 1.5s delay between requests:
- **Serial:** ~3 hours
- **20 workers (like WikEM):** ~10-15 minutes (with polite rate limiting per-worker)

---

## Architecture

```
litfl.com
    │
    ▼
┌─────────────────────┐
│  litfl_discovery.py  │  Parse sitemaps, discover all post URLs
└─────────┬───────────┘
          │ discovery/litfl_discovery.json
          ▼
┌─────────────────────┐
│  litfl_scraper.py    │  Per-page extraction (HTML → sections + metadata)
└─────────┬───────────┘
          │ output/raw/*.html, output/processed/*.json + *.md
          ▼
┌─────────────────────┐
│  litfl_bulk_scrape.py│  Parallel bulk scraping (ThreadPoolExecutor)
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  GCS Bucket          │  gs://clinical-assistant-457902-litfl/
│  processed/          │    cleaned markdown files
│  metadata/           │    per-article metadata JSON (images, author, etc.)
│  images/             │    downloaded images (ECGs, CTs, diagrams)
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  litfl_reindex.py    │  Upload → delete old corpus → create new → import
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Vertex AI RAG       │  Separate corpus: "litfl-foamed"
│  (us-west4)          │  text-embedding-005, chunk 1024/200
└─────────────────────┘
```

---

## File Structure

```
scrapers/
  litfl/
    litfl_discovery.py       # Sitemap parsing, URL collection & filtering
    litfl_scraper.py         # Per-page content extraction
    litfl_bulk_scrape.py     # Parallel bulk scraper (reuses litfl_scraper)
    litfl_reindex.py         # GCS upload + Vertex AI corpus rebuild
    litfl_rag_config.json    # Corpus ID, project config (auto-updated)
    requirements.txt         # Same deps as WikEM (requests, bs4, lxml)
    discovery/
      litfl_discovery.json   # Discovered URLs with metadata
    output/
      raw/                   # Raw HTML snapshots
      processed/             # Cleaned .json + .md files
      metadata/              # Scrape logs, error logs
```

---

## Implementation Details

### Phase 1: Discovery (`litfl_discovery.py`)

**Input:** LITFL sitemap index at `https://litfl.com/sitemap_index.xml`

**Process:**
1. Fetch sitemap index → find all `post-sitemap*.xml` files
2. Parse each sub-sitemap → collect all `<loc>` URLs with `<lastmod>` dates
3. Filter out:
   - The homepage (`https://litfl.com/`)
   - Any `/page/N/` pagination URLs
   - Any `/wp-admin/` or `/wp-content/` URLs
4. Extract slug from URL (e.g., `https://litfl.com/etomidate/` → `etomidate`)
5. Save to `discovery/litfl_discovery.json`

**Output format:**
```json
{
  "discovered_at": "2026-02-16T00:00:00Z",
  "source": "sitemap",
  "count": 7317,
  "urls": [
    {
      "url": "https://litfl.com/etomidate/",
      "slug": "etomidate",
      "lastmod": "2026-02-02T00:00:00Z"
    }
  ]
}
```

### Phase 2: Content Extraction (`litfl_scraper.py`)

**Key difference from WikEM:** LITFL is WordPress-based, not MediaWiki. Content lives in a different HTML structure.

**WordPress content structure:**
- Main content is inside `<article>` or `<div class="entry-content">`
- Headings are `<h4>` (most LITFL articles use h4 for section headers, not h2)
- Categories are in `<a>` tags with `/category/` URLs
- Author info and date in article header
- Images are standard `<img>` tags (no MediaWiki thumb system)

**Extraction per page:**
1. **Title** — `<h1>` or `<title>` tag
2. **Author(s)** — Extract from article header (linked author names)
3. **Date** — Published date from article header or `<time>` element
4. **Categories** — All `/category/` links on the page
5. **Sections** — Walk `<h4>` headings within entry-content:
   - CLASS, MECHANISM OF ACTION, DOSE, INDICATION, etc. (for CCC pharmacology)
   - Clinical Features, Differential Diagnosis, Management, etc. (for clinical topics)
   - ECG Findings, Key Features, etc. (for ECG library)
6. **Images** — All `<img>` within entry-content:
   - Skip tiny icons (<50px width)
   - Skip ad banners (Medmastery, Amazon affiliate)
   - Convert WordPress thumbnail URLs to full-res
   - Download to GCS: `images/{slug}/filename.jpg`
7. **References** — Extract reference section if present (many CCC articles have detailed refs)
8. **Related Links** — Internal LITFL links for cross-referencing

**Content filtering (skip non-clinical noise):**
- Skip share buttons, social links, comment sections
- Skip author bio boxes at the bottom
- Skip ad banners (Medmastery course promos)
- Skip "Unlock exclusive content" newsletter signup
- Strip affiliate link parameters

**Output: Processed Markdown (for RAG indexing)**
```markdown
# Etomidate

Source: [LITFL](https://litfl.com/etomidate/) (CC BY-NC-SA 4.0)
Authors: Chris Nickson
Date: 2026-02-02
Categories: CCC, Pharmacology

## CLASS

General anaesthetic / induction agent
Carboxylated imidazole derivative

## MECHANISM OF ACTION

Acts primarily as a positive allosteric potentiator of the GABA-A receptor...

## DOSE

IV Bolus: 0.2-0.6 mg/kg over 30-60 seconds for induction of anesthesia...

[... remaining sections ...]

## REFERENCES

[... citations with PMIDs ...]
```

**Output: Metadata JSON (for API image/citation lookup)**
```json
{
  "protocol_id": "etomidate",
  "title": "Etomidate",
  "url": "https://litfl.com/etomidate/",
  "authors": ["Chris Nickson"],
  "date": "2026-02-02",
  "categories": ["CCC", "Pharmacology"],
  "content_hash": "a1b2c3d4e5f6",
  "images": [
    {"url": "https://storage.googleapis.com/clinical-assistant-457902-litfl/images/etomidate/CCC_700_6.png", "alt": "CCC", "page": 0}
  ],
  "section_count": 14,
  "word_count": 2500
}
```

### Phase 3: Bulk Scraping (`litfl_bulk_scrape.py`)

Mirror the WikEM `wikem_bulk_scrape.py` pattern:
- `ThreadPoolExecutor` with configurable workers (default: 20)
- `ProgressTracker` with thread-safe counters
- `--resume` flag to skip already-scraped pages
- `--force` flag to re-scrape everything
- `--limit N` for testing
- `--retry-errors` to retry failed pages
- Rate limiting: 1.5s per request per worker
- Error tracking with `bulk_scrape_errors.json`

### Phase 4: Reindex (`litfl_reindex.py`)

Mirror `wikem_reindex.py`:
1. Upload all `.md` files to `gs://clinical-assistant-457902-litfl/processed/`
2. Delete old RAG corpus (if exists)
3. Create new corpus `"litfl-foamed"` with `text-embedding-005`
4. Batch import from GCS
5. Update `litfl_rag_config.json` with new corpus ID
6. Print Cloud Run env var update command

---

## API Changes (`api/rag_service.py`)

### New Environment Variable
```bash
LITFL_CORPUS_ID=<corpus_id>  # Set on Cloud Run em-protocol-api
```

### Code Changes

1. **Add LITFL corpus config** (alongside WikEM and PMC):
   ```python
   LITFL_CORPUS_ID = os.environ.get("LITFL_CORPUS_ID", "")
   LITFL_BUCKET = f"{PROJECT_ID}-litfl"
   ```

2. **Add `_get_litfl_metadata()` method** — same pattern as `_get_wikem_metadata()`:
   - Parse `gs://clinical-assistant-457902-litfl/processed/slug.md` → slug
   - Look up `metadata/slug.json` in LITFL GCS bucket
   - Cache results

3. **Add `fetch_litfl()` to `_retrieve_multi_source()`**:
   ```python
   def fetch_litfl():
       contexts = self._retrieve_contexts(query, self.litfl_corpus_name)
       for ctx in contexts:
           ctx["source_type"] = "litfl"
       return contexts
   ```

4. **Update `_generate_answer()`** source labels:
   ```python
   elif source_type == "litfl":
       source_label = "LITFL"
   ```

5. **Update `_get_images_from_contexts()`** to handle LITFL images
6. **Update `_get_source_key()`** for LITFL deduplication

---

## Frontend Changes (`frontend/app/page.tsx`)

### New State
```typescript
const [litflEnabled, setLitflEnabled] = useState(true);
```

### Source Selection UI

Add LITFL as a new toggleable source alongside WikEM and PMC in the "ED Universe" panel. Three options:

**Option A: Separate toggle (recommended)**
- 🌐 Globe section now has 3 sub-items: WikEM, LITFL, PMC Journals
- Each can be toggled independently
- LITFL gets its own icon (e.g., `Zap` ⚡ for "Fast Lane")

**Option B: LITFL grouped with WikEM under Globe**
- Globe toggle enables/disables all public sources
- Expandable to show WikEM ✓, LITFL ✓, PMC Journals ✓

### API Query Update
```typescript
const getEffectiveSources = (): string[] => {
  const sources: string[] = [];
  if (selectedEds.size > 0) sources.push("local");
  if (wikemEnabled) sources.push("wikem");
  if (litflEnabled) sources.push("litfl");  // NEW
  if (pmcEnabled && selectedJournals.size > 0) sources.push("pmc");
  return sources;
};
```

### Citation Display
- LITFL citations show as `LITFL: Article Title` (similar to `WikEM: Topic`)
- Clicking a LITFL citation opens the original litfl.com article URL

### Universe Preferences Persistence
Add `litflEnabled` to the `UNIVERSE_KEY` localStorage object:
```typescript
localStorage.setItem(UNIVERSE_KEY, JSON.stringify({
  wikemEnabled,
  litflEnabled,  // NEW
  pmcEnabled,
  selectedJournals: Array.from(selectedJournals),
}));
```

---

## API Endpoint Changes (`api/main.py`)

Update the `/query` endpoint to accept `"litfl"` in the `sources` list:

```python
# In the query endpoint, sources can now include "litfl"
# e.g., sources=["local", "wikem", "litfl", "pmc"]
```

---

## GCS Bucket Structure

```
gs://clinical-assistant-457902-litfl/
  processed/
    etomidate.md
    hyponatremia.md
    ecg-left-bundle-branch-block.md
    ...
  metadata/
    etomidate.json
    hyponatremia.json
    ecg-left-bundle-branch-block.json
    ...
  images/
    etomidate/
      CCC_700_6.png
    ecg-left-bundle-branch-block/
      LBBB_ECG_example.jpg
    ...
```

---

## RAG Corpus Config

```json
{
  "project_id": "clinical-assistant-457902",
  "project_number": "930035889332",
  "location": "us-west4",
  "corpus_id": "<TBD after creation>",
  "corpus_name": "projects/930035889332/locations/us-west4/ragCorpora/<TBD>",
  "corpus_display_name": "litfl-foamed",
  "embedding_model": "text-embedding-005",
  "chunk_size": 1024,
  "chunk_overlap": 200,
  "last_indexed": null
}
```

---

## Implementation Order

### Step 1: Scraper pipeline (~2-3 days)
1. Create `scrapers/litfl/` directory structure
2. Implement `litfl_discovery.py` — sitemap parsing
3. Implement `litfl_scraper.py` — WordPress content extraction
4. Implement `litfl_bulk_scrape.py` — parallel scraper
5. Test with `--test` on a few representative pages:
   - CCC pharmacology page (e.g., `etomidate`)
   - ECG library page (e.g., `left-bundle-branch-block-lbbb`)
   - Clinical case page
   - Eponym page
   - Toxicology page

### Step 2: Indexing pipeline (~1 day)
1. Create GCS bucket `clinical-assistant-457902-litfl`
2. Implement `litfl_reindex.py` — GCS upload + Vertex AI corpus
3. Run full scrape + index
4. Verify corpus in GCP console

### Step 3: API integration (~1 day)
1. Add `LITFL_CORPUS_ID` env var to `rag_service.py`
2. Add `fetch_litfl()` retrieval function
3. Add `_get_litfl_metadata()` for image/citation lookup
4. Update source labels in prompt
5. Deploy to Cloud Run with new env var

### Step 4: Frontend integration (~1 day)
1. Add `litflEnabled` state to `page.tsx`
2. Add LITFL toggle to ED Universe panel
3. Update `getEffectiveSources()` to include `"litfl"`
4. Update citation display for LITFL sources
5. Add `litflEnabled` to localStorage persistence
6. Deploy frontend

### Step 5: Documentation (~0.5 day)
1. Create `docs/LITFL_REINDEX_GUIDE.md` (mirror WIKEM_REINDEX_GUIDE.md)
2. Update `CLAUDE.md` with LITFL corpus info
3. Update `README.md`

---

## Scraping Challenges & Solutions

### 1. WordPress vs MediaWiki HTML Structure
**WikEM:** Content in `<div id="mw-content-text">`, headings are `<h2>`/`<h3>`  
**LITFL:** Content in `<div class="entry-content">` or `<article>`, headings are mostly `<h4>`

**Solution:** New extraction logic targeting WordPress article structure.

### 2. Mixed Content Types
LITFL has clinical articles, case studies, book reviews, conference reports, podcasts, etc.

**Solution:** Scrape everything (unified corpus per your preference). Tag with categories in metadata for future filtering if needed.

### 3. Image Handling
LITFL uses WordPress media library with responsive `srcset` attributes and lazy loading (`data-src`).

**Solution:**
- Check for `data-src` (lazy load) before `src`
- Parse `srcset` to get highest-resolution version
- Skip Medmastery ad banners, social icons, author avatars
- Filter by size (skip < 50px width)

### 4. Ad/Promotional Content
Many LITFL pages have Medmastery course banners, Amazon affiliate links, newsletter signup forms.

**Solution:** Strip known ad patterns:
- Elements with `medmastery` in URLs
- Amazon affiliate links (keep in references section only)
- Newsletter signup `<form>` elements
- Social share buttons

### 5. Rate Limiting
7,300 pages is ~4x more than WikEM (1,900 pages).

**Solution:**
- Same polite 1.5s delay per request
- 20 workers = ~10-15 min total
- Polite User-Agent header with contact email

### 6. Slug Conflicts
Some LITFL slugs might be numeric (e.g., `284-2`) or have special characters.

**Solution:** Sanitize slugs for filenames (replace special chars, handle numeric-only slugs).

---

## Cloud Run Environment Variables (after indexing)

```bash
gcloud run services update em-protocol-api \
  --region us-central1 \
  --update-env-vars LITFL_CORPUS_ID=<new_corpus_id>
```

---

## Testing Plan

1. **Single page test:** `python litfl_scraper.py --test` (scrape Etomidate)
2. **Content type coverage:** Test one page from each major category
3. **Image download:** Verify ECG images download and serve from GCS
4. **Bulk scrape (limited):** `python litfl_bulk_scrape.py --workers 5 --limit 50`
5. **Full scrape:** `python litfl_bulk_scrape.py --workers 20`
6. **Reindex:** `python litfl_reindex.py`
7. **API test:** Query with `sources=["litfl"]` — verify retrieval
8. **Frontend test:** Toggle LITFL on/off, verify citations
9. **Cross-source test:** Query with all sources enabled — verify LITFL, WikEM, PMC coexist

---

## Maintenance Schedule

- **Reindex every 6 months** (same cadence as WikEM)
- **Full re-scrape:** Use `litfl_bulk_scrape.py --workers 20 --force`
- **Incremental update:** Use `--resume` to only scrape new pages (compare `lastmod` dates from sitemap)
- **Time required:** ~20-25 minutes total (scrape ~15 min + upload/index ~5 min)
