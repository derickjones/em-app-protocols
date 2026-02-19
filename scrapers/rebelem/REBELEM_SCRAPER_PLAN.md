# REBEL EM Scraper Plan

## Overview
Scrape ~1,247 evidence-based EM posts from [rebelem.com](https://rebelem.com/) and index into a Vertex AI RAG corpus, following the same architecture as LITFL and WikEM scrapers.

**License:** CC BY-NC-ND 3.0 — attribution required, non-commercial, no derivatives.

---

## Phase 1: Discovery (`rebelem_discovery.py`)
Parse WordPress sitemaps to discover all post URLs.

- **Sitemap index:** `https://rebelem.com/sitemap_index.xml`
- **Post sitemaps:** `post-sitemap.xml` (1,000 URLs) + `post-sitemap2.xml` (247 URLs) = **~1,247 posts**
- Filter to post sitemaps only (skip page, category, author, rebel-review sitemaps)
- Output: `discovery/rebelem_discovery.json` with URL, slug, lastmod for each post

### Filtering Strategy
Some REBEL EM posts are non-clinical (conference recaps, book clubs, productivity tips, slide design). We index everything — the RAG retriever will rank clinical content higher for clinical queries naturally.

---

## Phase 2: Scraper (`rebelem_scraper.py`)
Single-page scraper that extracts structured content from any REBEL EM post.

### Site-Specific HTML Structure (WordPress + Elementor)
REBEL EM uses WordPress with the Elementor page builder. Key differences from LITFL:

| Element | LITFL | REBEL EM |
|---------|-------|----------|
| Platform | WordPress (Blocksy theme) | WordPress (Elementor) |
| Content container | `div.entry-content` inside `<article>` | `div.entry-content` or `div.elementor-widget-theme-post-content` |
| Headings | `h2-h6.wp-block-heading` | `h3` (mostly), some `h2` |
| Images | `figure.wp-block-image` | `figure.wp-block-image`, `div.wp-block-image`, Elementor image widgets |
| Metadata | Yoast JSON-LD `@graph` | Yoast JSON-LD `@graph` (same plugin) |
| Author info | In meta elements | "Guest Post By:" section + "Post-Peer Reviewed By: Salim R. Rezaie" |
| Cite block | None | `Cite this article as:` block at bottom |
| Ads/noise | Medmastery, m-a-box | WooCommerce, ad space CTAs, cookie consent |

### Content Extraction
1. **Fetch** page HTML with 10s crawl delay (per robots.txt)
2. **Parse** with BeautifulSoup
3. **Extract metadata** from Yoast JSON-LD schema (same as LITFL — author, dates, description, keywords, categories)
4. **Extract HTML metadata** — title from `<h1>`, author from Yoast or "Guest Post By" section, medical category from links, tags from tag links
5. **Find content div** — `div.entry-content` inside `<article>` (same pattern as LITFL)
6. **Strip noise** — cookie banners, ad CTAs ("WANT TO SUPPORT REBELEM?"), social sharing, related posts, navigation (prev/next), footer, guest post bio section, WooCommerce elements
7. **Extract sections** — walk children, split on `h2`/`h3` headings, capture content between headings as markdown
8. **Extract images** — from `figure.wp-block-image` elements, get best URL (data-orig-file → data-lazy-src → srcset → src), capture alt/caption/section context
9. **Download images to GCS** — bucket `clinical-assistant-457902-rebelem`, path `images/{slug}/{filename}`
10. **Build markdown** — title header + attribution + sections with clean text
11. **Save outputs:**
    - `output/raw/{slug}.html` — raw HTML
    - `output/processed/{slug}.md` — clean markdown for RAG indexing
    - `output/processed/{slug}.json` — structured data (metadata, sections, images, references)

### Elements to Strip
```python
STRIP_CLASSES = [
    "elementor-widget-nav-menu",     # Navigation
    "elementor-widget-sidebar",      # Sidebar widgets
    "cookie-consent",                # Cookie banner
    "woocommerce",                   # Shop elements
    "sharedaddy",                    # Social sharing
    "jp-relatedposts",               # Related posts
    "post-navigation",               # Prev/next navigation
    "comments-area",                 # Comments
    "comment-respond",               # Comment form
]
```

### Image Filtering
```python
FILTER_IMAGE_URLS = [
    "rebelem-logo",
    "gravatar.com",
    "rosh-review",                   # Sponsored Rosh Review images
    "woocommerce",
    "rebel-em-logo",
    "cropped-rebel",
    "ad-space",
]
```

### Markdown Output Format
```markdown
# Etomidate Vs. Ketamine: A Systematic Review and Meta-Analysis

**Source:** REBEL EM | **Author:** Anthony Ascione, DO | **Reviewed by:** Salim R. Rezaie, MD
**Date:** November 3, 2022 | **Category:** Resuscitation
**License:** CC BY-NC-ND 3.0 — Attribution: Salim R. Rezaie, MD
**URL:** https://rebelem.com/etomidate-vs-ketamine-a-systematic-review-and-meta-analysis/

## Background
Rapid sequence intubation (RSI) induction agent selection remains...

## What They Did
...

## Primary Results
...

## Our Conclusions
...

## References
1. Albert SG et al. The effect of etomidate... PMID: 21373823
...
```

---

## Phase 3: Bulk Scraper (`rebelem_bulk_scrape.py`)
Parallel scraper with resume support — identical pattern to LITFL.

- Load discovery JSON
- Track progress in `output/metadata/bulk_scrape_log.json`
- Track errors in `output/metadata/bulk_scrape_errors.json`
- Default 3 workers with 10s delay (REBEL EM robots.txt: `Crawl-delay: 10`)
- Resume support (`--resume`)
- Retry failed pages (`--retry-errors`)
- Optional `--no-gcs` for local-only testing

### Estimated Time
- ~1,247 posts × 10s delay = ~3.5 hours with 1 worker
- With 3 workers: ~1.2 hours (respecting crawl delay per-worker)

---

## Phase 4: Indexer (`rebelem_indexer.py`)
Create a Vertex AI RAG corpus and index all markdown files — identical pattern to LITFL indexer.

- **Corpus display name:** `rebelem-foamed`
- **Corpus description:** "Evidence-based emergency medicine reviews from REBEL EM (rebelem.com) — trial analyses, clinical guidelines, critical appraisals"
- **Embedding model:** `text-embedding-005`
- **Chunk size:** 1024, overlap 200 (same as all other corpora)
- **GCS bucket:** `clinical-assistant-457902-rebelem`
- Upload markdown to `gs://clinical-assistant-457902-rebelem/processed/{slug}.md`
- Upload metadata to `gs://clinical-assistant-457902-rebelem/metadata/{slug}.json`
- Save corpus config to `rebelem_rag_config.json`

### Estimated Indexing Time
- ~1,247 files × ~5s/file = ~1.7 hours with 1 worker

---

## Phase 5: Backend Integration (`api/rag_service.py` + `api/main.py`)
Add REBEL EM as a 5th source — same pattern as LITFL.

### rag_service.py
```python
REBELEM_CORPUS_ID = os.environ.get("REBELEM_CORPUS_ID", "<new-corpus-id>")
REBELEM_BUCKET = f"{PROJECT_ID}-rebelem"
# Add rebelem_corpus_name to __init__
# Add "rebelem" case to query_stream() corpus selection
# Add _get_rebelem_metadata() method (same pattern as _get_litfl_metadata)
```

### main.py
```python
# Update default sources:
sources: List[str] = Field(default=["local", "wikem", "pmc", "litfl", "rebelem"])

# Add REBELEM citation handler in _build_citations():
if source_type == "rebelem":
    # Same pattern as LITFL — slug from GCS path, metadata lookup, link to rebelem.com
```

### Cloud Run env var
```
REBELEM_CORPUS_ID=<new-corpus-id>
```

---

## Phase 6: Frontend Integration (`frontend/app/page.tsx`)
Add REBEL EM toggle to the Ed Universe sidebar.

- Download REBEL EM logo → `frontend/public/logos/rebelem-logo.png`
- Add state: `rebelemEnabled`, `rebelemExpanded`
- Add toggle UI block (after LITFL, before PMC) with:
  - Orange checkbox color (`bg-orange-500 border-orange-500`)
  - Logo image
  - "REBEL EM" label
  - "1,247" count
  - Expandable description: "Evidence-based EM reviews and critical appraisals of landmark trials — etomidate vs ketamine, sepsis management, PE workup, and more."
- Add `"rebelem"` to default sources array and save/load logic
- Add REBEL EM citation rendering (orange badge, rebelem.com links)

---

## File Structure
```
scrapers/rebelem/
├── rebelem_discovery.py      # Phase 1: Sitemap discovery
├── rebelem_scraper.py        # Phase 2: Single-page scraper
├── rebelem_bulk_scrape.py    # Phase 3: Parallel bulk scraper
├── rebelem_indexer.py        # Phase 4: RAG corpus indexer
├── rebelem_rag_config.json   # Auto-generated corpus config
├── requirements.txt          # Python dependencies
├── REBELEM_SCRAPER_PLAN.md   # This file
├── discovery/
│   └── rebelem_discovery.json
└── output/
    ├── raw/                  # Raw HTML files
    ├── processed/            # Clean markdown + JSON
    └── metadata/             # Bulk scrape logs
```

---

## Execution Order
```bash
# 1. Discovery
cd scrapers/rebelem
python3 rebelem_discovery.py --sitemap

# 2. Test single page
python3 rebelem_scraper.py --test

# 3. Bulk scrape (~1.2 hours with 3 workers)
python3 rebelem_bulk_scrape.py --workers 3

# 4. Create corpus (one-time)
python3 rebelem_indexer.py --create-corpus

# 5. Index all (~1.7 hours)
python3 rebelem_indexer.py --index-all --workers 1

# 6. Backend: add REBELEM_CORPUS_ID to rag_service.py + main.py
# 7. Deploy backend with new env var
# 8. Frontend: add REBEL EM toggle + logo
# 9. Deploy frontend
```

---

## Risk Mitigation
- **Crawl delay:** 10s per robots.txt — respected in scraper
- **Attribution:** Every markdown file includes CC BY-NC-ND 3.0 attribution to Salim R. Rezaie, MD
- **No derivatives:** RAG retrieves and quotes original text with attribution, does not create derivative works
- **Non-commercial:** Educational/clinical tool, not monetized
