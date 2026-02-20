# LearnPICU Scraper Plan

## ⚠️ CRITICAL: Licensing Issue

**LearnPICU is NOT open-licensed.** Every page states:

> © Kevin Kuo, M.D., MHPE. All Rights Reserved.  
> For permission for additional use of this content please contact Kevin Kuo at kkuo@stanford.edu

This is fundamentally different from every other source we've scraped:

| Source | License | Status |
|--------|---------|--------|
| WikEM | CC BY-SA 3.0 | ✅ Open |
| LITFL | CC BY-NC-SA 4.0 | ✅ Open |
| REBEL EM | CC BY-NC-ND 4.0 | ✅ Open |
| ALiEM | CC BY-NC-ND 3.0 | ✅ Open |
| PMC | Open Access | ✅ Open |
| **LearnPICU** | **All Rights Reserved** | ❌ **Requires permission** |

### Recommendation

**You must contact Dr. Kevin Kuo (kkuo@stanford.edu) and obtain written permission before scraping.** Explain:
1. The educational/clinical decision support purpose
2. That content will be used as RAG context (not republished verbatim)
3. Attribution will be preserved on every retrieved chunk
4. The tool is for internal/institutional use (Mayo)

If permission is granted, proceed with the plan below.

---

## Site Overview

- **URL**: https://www.learnpicu.com
- **Platform**: Google Sites (new Google Sites, not classic)
- **Also known as**: "Custer's Core Curriculum"
- **Editor**: Dr. Kevin Kuo, M.D., MHPE (Stanford)
- **Content**: Summaries of core topics in pediatric critical care medicine, with practice board-type questions, supporting references, and summaries of seminal articles
- **No robots.txt** (returns 404)
- **No sitemap.xml** (returns 404)

## Site Structure

### Top-Level Categories (27 total)

These serve as both standalone content pages and parent category pages:

| Category | URL | Subcategory Count |
|----------|-----|-------------------|
| Acid Base Disorders | `/acid-base-disorders` | 0 (standalone) |
| Burns/Inhalational Injury | `/burns-inhalational-injury` | 0 |
| **Cardiology** | `/cardiology` | **8** (arrhythmias, cardiopulmonary-interactions, congenital-heart-disease, hemodynamics, hypertensive-urgency-emergencies, pulmonary-embolism, pulmonary-hypertension, tamponade) |
| Communication | `/communication` | 0 |
| CPR | `/cpr` | 0 |
| ECMO | `/ecmo` | 0 |
| End of Life & Palliative Care | `/end-of-life-palliative-care` | 0 |
| Endocrine | `/endocrine` | TBD |
| Endotheliopathy | `/endotheliopathy` | 0 |
| Fluids Electrolytes and Nutrition | `/fluids-electrolytes-and-nutrition` | TBD |
| GI | `/gi` | TBD |
| Health Disparities/DEI | `/health-disparitiesdei` | 0 |
| Hematology/Oncology | `/oncology` | TBD |
| **Infectious Disease** | `/infectious-disease` | **5** (antibiotics-review, bronchiolitis, pertussis, pneumonia-empyema, Sepsis) |
| Medical Education | `/medical-education` | 0 |
| Metabolic Emergencies | `/metabolic-emergencies` | 0 |
| Monitoring | `/monitoring` | TBD |
| **Nephrology** | `/nephrology` | **2** (renal-failure, renal-replacement-therapy) |
| **Neurology** | `/neurology` | **7** (brain-death, delirium, ICP, neuromuscular-disorders, sedation, status-epilepticus, stroke) |
| Personal Finance 101 | `/personal-finance-101` | 0 |
| Pharmacology 101 | `/pharmacology-101` | 0 |
| PICU Prophylaxis | `/picu-prophylaxis` | 0 |
| Research Statistics Basics | `/basic-research-statistics` | 0 |
| **Respiratory** | `/respiratory` | **10** (aprv, ARDS, drowning, hfov, intubation-rsi, Mechanical-Ventilation, noninvasive-ventilation, oxygenation-oxygen-transport, status-asthmaticus, upper-airway-abnormalities) |
| Shock | `/shock` | 0 |
| Toxins/Ingestions | `/toxidromes` | TBD |
| Trauma | `/trauma` | TBD |
| Ultrasound | `/ultrasound` | TBD |
| Vascular Access/Tube Thoracostomy | `/vascular-access` | TBD |

**Estimated total pages: 60–100** (27 categories + ~35 known subtopics + unknown subtopics in TBD categories)

### URL Patterns

- Top-level: `https://www.learnpicu.com/{slug}`
- Subcategory: `https://www.learnpicu.com/{category}/{subtopic}`
- **Case-sensitive URLs** — e.g., `/infectious-disease/Sepsis` (capital S), `/respiratory/ARDS`, `/neurology/ICP`
- Some category URL slugs don't match display names: "Hematology/Oncology" → `/oncology`, "Toxins/Ingestions" → `/toxidromes`

### Content Format

Each topic page contains:
- **Rich text content** with headers (H1, H2, H3), paragraphs, bullet lists, tables
- **Educational images** hosted on `lh3.googleusercontent.com/sitesv/...` (Google's CDN)
- **Contributing author** credits at bottom of content pages
- **Cross-links** between related topics
- **Practice questions** (mentioned on home page, may be separate sections or pages)
- **References/bibliography** sections
- **No publication dates** visible (Google Sites doesn't expose these)

### Technical Characteristics (Google Sites)

- HTML is rendered server-side but uses Google Sites proprietary markup
- No standard `<article>` tags — content is in deeply nested `<div>` structures
- Images use Google's CDN URLs with resize parameters (e.g., `=w1280`)
- Navigation sidebar is present on every page with the full topic list
- Footer with copyright notice on every page
- No API available — must scrape HTML

---

## Scraper Architecture

### Phase 1: Discovery (`learnpicu_discovery.py`)

Since there's no sitemap, discovery must crawl the navigation:

1. **Fetch any category page** (e.g., `/cardiology`) — the sidebar nav lists ALL top-level categories
2. **For each category page**, extract subtopic links (they appear as child links under the category in the nav AND as link cards in the main content)
3. **Build complete URL list** and save to `discovery/learnpicu_discovery.json`

```python
# Discovery approach
SEED_URL = "https://www.learnpicu.com/cardiology"  # Any page will do

# Step 1: Extract all top-level categories from sidebar nav
# Step 2: Visit each category page
# Step 3: Extract subtopic links from the main content area
# Step 4: Deduplicate and save
```

### Phase 2: Scraper (`learnpicu_scraper.py`)

For each discovered URL:

1. **Fetch HTML** with polite rate limiting (2.0s delay — small site, be extra respectful)
2. **Parse content** — Extract from the main content `<div>`, skipping:
   - Navigation sidebar
   - Footer / copyright block
   - Google Sites boilerplate
3. **Extract structured data**:
   - `title` — from `<h1>` tag
   - `category` — from URL path (first segment)
   - `sections` — parsed from heading hierarchy
   - `images` — `lh3.googleusercontent.com` URLs with alt text
   - `references` — from References/Bibliography section
   - `contributing_authors` — from author credits
   - `cross_links` — links to other LearnPICU topics
4. **Generate outputs**:
   - `raw/{slug}.html` — original HTML
   - `processed/{slug}.json` — structured JSON
   - `processed/{slug}.md` — clean Markdown (for RAG indexing)

### Phase 3: Bulk Scrape (`learnpicu_bulk_scrape.py`)

- Iterate through all discovered URLs
- Rate limit at 2.0s (small site)
- Save progress for resume capability
- Upload to GCS bucket: `clinical-assistant-457902-learnpicu`

### Phase 4: Indexing (`learnpicu_reindex.py`)

- Create Vertex AI RAG corpus: `learnpicu-corpus`
- Upload processed `.md` files from GCS to RAG API
- Chunking: 1024 tokens / 200 overlap (same as other sources)
- Embedding: `text-embedding-005`

---

## Google Sites Parsing Strategy

Google Sites HTML is non-standard. Key challenges and solutions:

### Challenge 1: Finding the Main Content

Google Sites wraps content in deeply nested divs. Strategy:
- Look for the `<h1>` element containing the page title
- The main content container is the nearest common ancestor of the `<h1>` and the subsequent content elements
- Alternatively: Find the div with `role="main"` or `data-page-id`

### Challenge 2: Image Extraction

Images use Google CDN URLs like:
```
https://lh3.googleusercontent.com/sitesv/APaQ0S...=w1280
```

Strategy:
- Extract all `<img>` tags from the content area
- Filter out the site logo (appears in header/footer)
- Preserve resize parameter for quality (`=w1280` or `=s0` for original)
- Map images to their nearest heading for context

### Challenge 3: Stripping Navigation

Every page has the full sidebar nav. Strategy:
- Identify the sidebar/nav container (typically the left column)
- Strip everything outside the main content column
- Strip the footer copyright block
- Strip "Additional Links" section (it's the nav repeated in the content)

### Challenge 4: No Publication Dates

Google Sites doesn't expose page creation/modification dates. Strategy:
- Set `scraped_at` timestamp
- Omit `published_date` from metadata
- Use `"date": null` in JSON output

---

## File Structure

```
scrapers/
  learnpicu/
    learnpicu_discovery.py     # URL discovery via nav crawling
    learnpicu_scraper.py       # Single-page scraper + content parser
    learnpicu_bulk_scrape.py   # Bulk scrape orchestrator
    learnpicu_reindex.py       # Vertex AI RAG indexing
    learnpicu_rag_config.json  # RAG corpus configuration
    requirements.txt           # beautifulsoup4, requests, google-cloud-storage, etc.
    discovery/
      learnpicu_discovery.json # All discovered URLs
    output/
      raw/                     # Raw HTML files
      processed/               # JSON + Markdown files
      metadata/
        bulk_scrape_log.json
        bulk_scrape_errors.json
```

---

## Output Formats

### JSON (`processed/{slug}.json`)
```json
{
  "source": "learnpicu",
  "url": "https://www.learnpicu.com/cardiology/arrhythmias",
  "slug": "arrhythmias",
  "title": "Arrhythmias",
  "category": "Cardiology",
  "sections": [
    {
      "heading": "Overview",
      "level": 2,
      "content": "..."
    }
  ],
  "images": [
    {
      "url": "https://lh3.googleusercontent.com/sitesv/...",
      "alt": "ECG showing SVT",
      "context_heading": "Supraventricular Tachycardia"
    }
  ],
  "references": ["..."],
  "contributing_authors": ["..."],
  "cross_links": ["/cardiology/hemodynamics", "/shock"],
  "scraped_at": "2025-01-15T...",
  "content_hash": "sha256:...",
  "license": "All Rights Reserved - Used with permission from Dr. Kevin Kuo",
  "attribution": "LearnPICU.com - © Kevin Kuo, M.D., MHPE"
}
```

### Markdown (`processed/{slug}.md`)
```markdown
# Arrhythmias

**Source**: [LearnPICU](https://www.learnpicu.com/cardiology/arrhythmias)
**Category**: Cardiology
**Attribution**: © Kevin Kuo, M.D., MHPE — LearnPICU.com. Used with permission.

## Overview
...

## References
...
```

---

## Integration Plan

Once scraped and indexed:

1. **Backend** (`api/rag_service.py`):
   - Add `LEARNPICU_CORPUS_ID` env var
   - Add `learnpicu` GCS bucket
   - Add metadata/image/citation handlers (similar to existing sources)

2. **Frontend** (`frontend/app/page.tsx`):
   - Add LearnPICU toggle in Ed Universe section
   - Pick a color theme (e.g., emerald-500 for pediatric green)
   - Add LearnPICU logo/icon
   - Add citation formatting

3. **Cloud Run**: Redeploy with new corpus ID env var

---

## Estimated Scale

| Metric | Estimate |
|--------|----------|
| Total pages | 60–100 |
| Avg content per page | ~2,000–5,000 words |
| Total content | ~200K–400K words |
| Images | ~200–500 |
| Scrape time | ~3–5 minutes (with 2s delay) |
| GCS storage | ~5–15 MB |

This is the **smallest** source we've integrated — roughly 1/50th the size of WikEM.

---

## Implementation Order

1. ⏸️ **Get permission from Dr. Kevin Kuo** (kkuo@stanford.edu)
2. `learnpicu_discovery.py` — Build URL list (~30 min)
3. `learnpicu_scraper.py` — Content parser (~2 hrs, Google Sites parsing is tricky)
4. `learnpicu_bulk_scrape.py` — Orchestrator (~30 min, copy from existing)
5. Test scrape + review output quality
6. `learnpicu_reindex.py` — RAG indexing (~30 min)
7. Backend integration (~30 min)
8. Frontend integration (~30 min)
9. Deploy + test

**Total dev time**: ~5 hours (assuming permission granted)

---

## Topics to Exclude from Scraping

These are non-clinical and should be filtered during discovery:
- Personal Finance 101
- Medical Education
- Health Disparities/DEI (may want to include — discuss)
- Research Statistics Basics
- Communication
