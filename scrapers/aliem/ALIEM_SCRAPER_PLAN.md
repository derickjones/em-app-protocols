# ALiEM Scraper Plan

## Overview
Scrape ~2,500+ evidence-based EM posts from [aliem.com](https://www.aliem.com/) and index into a Vertex AI RAG corpus, following the same architecture as LITFL, WikEM, and REBEL EM scrapers.

---

## ⚠️ CRITICAL: Licensing Assessment

### The Problem — Split License
ALiEM uses a **split licensing model** that is significantly more restrictive than REBEL EM or LITFL:

| Content Type | License | Scrapeable? |
|-------------|---------|-------------|
| **Paucis Verbis (PV) Cards** | CC BY-NC-ND 3.0 | ✅ Yes — same as REBEL EM |
| **MEdIC Series** | CC BY-NC-ND 3.0 | ✅ Yes — same as REBEL EM |
| **All other blog content** | **"All Rights Reserved"** | ⚠️ **Legally ambiguous** |

**Footer text (every page):**
> "ALiEM by ALiEM.com is copyrighted as 'All Rights Reserved' except for our Paucis Verbis cards and MEdIC Series, which are Creative Commons Attribution-NonCommercial-NoDerivs 3.0 Unported License."

**Page header (disclaimer-privacy-copyright) contradicts this:**
> "The content falls under the Creative Commons Attribution-NonCommercial-NoDerivs 4.0 Unported License"
> *(But links to CC BY-NC-ND 3.0 URL — inconsistent)*

### robots.txt Signals (Cloudflare)
```
Content-Signal: search=yes, ai-train=no
```
- `ai-train=no` — Explicitly blocks AI training use
- `ai-input` — **NOT specified** (neither granted nor restricted)
- Per Cloudflare spec: "If the token is missing... the website operator neither grants nor restricts permission"

### Blocked Bots
```
User-agent: Amazonbot, Applebot-Extended, Bytespider, CCBot, ClaudeBot, 
            Google-Extended, GPTBot, meta-externalagent
Disallow: /
```

### Recommendation: Two-Track Approach

**Track A — Safe (PV Cards + MEdIC Series only):**
- ~120-150 PV Cards (clinical reference cards — extremely high value)
- ~30-40 MEdIC Series posts (ethics case discussions)
- CC BY-NC-ND 3.0 — same legal basis as REBEL EM
- **Recommend starting here**

**Track B — Full blog (requires permission):**
- ~2,500+ clinical posts (tricks of the trade, splinter series, SAEM clinical images, AIR modules, etc.)
- "All Rights Reserved" — cannot legally reproduce without permission
- **Action:** Email ALiEM team (contact form on site) requesting permission for educational RAG use with attribution
- If granted → proceed with full scrape
- If denied → stick to Track A

### For This Plan
We document the **full scrape architecture** (both tracks) so everything is ready regardless of which track is pursued. Track A (PV Cards + MEdIC) can begin immediately. Track B awaits permission.

---

## Site Architecture

### Platform
- **CMS:** WordPress with Yoast SEO
- **CDN:** Cloudflare
- **Images:** WordPress media library + `wp-content/uploads/` (via `i0.wp.com` CDN)
- **No page builder** (unlike REBEL EM's Elementor) — standard WordPress theme with `entry-content`

### Content Categories (102 categories)
Key clinical categories from the category sitemap:

| Category | Example Content |
|----------|----------------|
| `emergency-medicine-clinical/` | Main clinical content hub |
| `emergency-medicine-clinical/pv-card/` | **Paucis Verbis cards** (CC licensed) ✅ |
| `academic/medic-series/` | **MEdIC ethics cases** (CC licensed) ✅ |
| `emergency-medicine-clinical/tricks-of-the-trade/` | Clinical tricks and tips |
| `emergency-medicine-clinical/system/cv/ecg/` | ECG interpretation |
| `emergency-medicine-clinical/system/tox-meds/` | Toxicology, pharmacology |
| `emergency-medicine-clinical/pediatrics/pem-pearls/` | Pediatric EM pearls |
| `emergency-medicine-clinical/pediatrics/pem-pocus/` | Pediatric POCUS |
| `emergency-medicine-clinical/system/orthopedic/splinter/` | Orthopedic case series |
| `emergency-medicine-clinical/saem-clinical-images/` | SAEM clinical images |
| `emergency-medicine-clinical/system/tox-meds/acmt-visual-pearls/` | ACMT toxicology pearls |
| `emergency-medicine-clinical/approved-instructional-resources-air-series/` | AIR modules |
| `emergency-medicine-clinical/system/radiology/ultrasound/` | Ultrasound |
| `emergency-medicine-clinical/guideline/` | Guideline reviews |
| `emergency-medicine-clinical/system/orthopedic/emrad/` | Radiology interpretation |

### Sitemaps
- **Index:** `https://www.aliem.com/sitemap_index.xml` (Yoast SEO)
- **Post sitemaps:** `post-sitemap.xml`, `post-sitemap2.xml`, `post-sitemap3.xml`
- 3 post sitemaps = **~2,500-3,000 posts** (WordPress default 1,000/sitemap)
- **Category sitemap:** `category-sitemap.xml` (102 categories)
- **Page sitemap:** `page-sitemap.xml`
- Also has: attachment sitemaps (6), author, post_tag, post_format, mailpoet, element_category

### Content Date Range
- Earliest posts: ~2009-2010 (founded 2009 by Dr. Michelle Lin)
- Latest posts: 2026 (scheduled/future-dated SAEM clinical images)
- Active publishing: ~1-3 posts/week currently

---

## Phase 1: Discovery (`aliem_discovery.py`)
Parse WordPress sitemaps to discover all post URLs.

- **Sitemap index:** `https://www.aliem.com/sitemap_index.xml`
- **Post sitemaps:** `post-sitemap.xml` + `post-sitemap2.xml` + `post-sitemap3.xml`
- Filter to post sitemaps only (skip page, attachment, category, tag, author, mailpoet, element_category sitemaps)
- Output: `discovery/aliem_discovery.json` with URL, slug, lastmod for each post

### Track A Filtering (PV Cards + MEdIC only)
For the safe CC-licensed track, filter URLs by slug pattern:
```python
PV_CARD_PATTERNS = [
    "/paucis-verbis-",
    "/pv-card-",
    "/pv-",               # Some older cards use just "pv-"
    "/tox-meds-pv-cards",
]
MEDIC_PATTERNS = [
    "/medic-series-",
    "/medic-case-",
    "/medic-",
]
```

Discovery should tag each URL with its track (A or B) based on these patterns.

### URL Estimate
- **Track A:** ~150-180 PV Cards + ~40-50 MEdIC posts = ~200 CC-licensed posts
- **Track B:** ~2,300+ additional "All Rights Reserved" posts
- **Total:** ~2,500+

---

## Phase 2: Scraper (`aliem_scraper.py`)
Single-page scraper that extracts structured content from any ALiEM post.

### Site-Specific HTML Structure (Standard WordPress + Yoast)

| Element | REBEL EM | ALiEM |
|---------|----------|-------|
| Platform | WordPress + Elementor | WordPress (standard theme) |
| Content container | `div.elementor-widget-container` | `div.entry-content` inside `<article>` |
| Headings | `h3` (mostly) | `h2`, `h3` (standard WordPress) |
| Images | Elementor image widgets | `figure.wp-block-image`, `<img>` in `<p>`, `wp-content/uploads/` |
| Image CDN | Direct `rebelem.com/wp-content/` | `i0.wp.com/www.aliem.com/wp-content/` (Jetpack CDN) |
| Metadata | Yoast JSON-LD `@graph` | Yoast JSON-LD `@graph` (same) |
| Author info | "Guest Post By:" | Author byline below title, author archive links |
| Categories | Tags at bottom | Category links in header area |
| Ads/noise | WooCommerce, Ezoic | Social sharing (sharedaddy), related posts (jp-relatedposts) |

### Content Extraction
1. **Fetch** page HTML with polite delay (5s — no `Crawl-delay` in robots.txt, but Cloudflare protection warrants caution)
2. **Parse** with BeautifulSoup
3. **Extract metadata** from Yoast JSON-LD schema (author, dates, description, categories, tags)
4. **Extract HTML metadata** — title from `<h1>`, author from byline, date, categories from links
5. **Find content div** — `<article>` → `div.entry-content` (standard WordPress)
6. **Strip noise:**
   - Social sharing buttons (`sharedaddy`, `sd-content`)
   - Related posts (`jp-relatedposts`)
   - Navigation (Previous/Next links)
   - Author bio box at bottom
   - Comments section
   - Footer elements (EDITORS' PICKS, newsletter signup, mission statement)
   - Book/merchandise ads ("Tricks book ad")
7. **Extract sections** — walk children, split on `h2`/`h3` headings, capture content between headings as markdown
8. **Extract images** — from `<figure>`, `<img>` tags. ALiEM images use Jetpack CDN (`i0.wp.com`):
   - Get original URL from `data-orig-file` or parse Jetpack URL to get original
   - Handle `?resize=`, `?w=`, `?fit=` query params
   - Capture alt text and caption
9. **Download images to GCS** — bucket `clinical-assistant-457902-aliem`, path `images/{slug}/{filename}`
10. **Build markdown** — title header + attribution + sections with clean text
11. **Save outputs:**
    - `output/raw/{slug}.html` — raw HTML
    - `output/processed/{slug}.md` — clean markdown for RAG indexing
    - `output/processed/{slug}.json` — structured data (metadata, sections, images, references)

### PV Card Specifics
PV Cards are clinical reference cards, often with a single image/PDF card. The scraper should:
- Detect PV Card posts (by URL slug or category)
- Extract the card image (often the main content)
- Extract reference citations
- Include "PV Card" tag in metadata for RAG ranking

### Elements to Strip
```python
STRIP_CLASSES = [
    "sharedaddy",               # Social sharing buttons
    "sd-content",               # Sharing content container
    "sd-block",                 # Sharing block
    "jp-relatedposts",          # Jetpack related posts
    "post-navigation",          # Previous/Next navigation
    "comments-area",            # Comments section
    "comment-respond",          # Comment form
    "author-box",               # Author bio box
    "entry-footer",             # Footer metadata
    "widget-area",              # Sidebar widgets
    "site-footer",              # Site footer
]

STRIP_IDS = [
    "comments",
    "respond",
]
```

### Image Filtering
```python
FILTER_IMAGE_URLS = [
    "gravatar.com",             # Author avatars
    "aliem-logo",               # Site logo
    "cropped-aliem",            # Cropped site logo
    "advertisement",            # Ad images
    "sponsor",                  # Sponsored content images
    "tricks-of-trade-book",     # Book promotion
    "favicon",                  # Favicon
    "aliemcards.com",           # External ALiEM Cards site
]
```

### Cloudflare Handling
ALiEM is behind Cloudflare, which may:
- Rate limit aggressive scraping
- Serve JS challenges for bot-like behavior
- Block known scraper user agents

Mitigation:
```python
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; EMProtocolBot/1.0; educational-clinical-tool)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}
REQUEST_DELAY = 5  # Conservative — no Crawl-delay specified but Cloudflare protection
REQUEST_TIMEOUT = 30  # Higher timeout for Cloudflare
MAX_RETRIES = 3
```

### Markdown Output Format
```markdown
# Paucis Verbis card: Hyperkalemia management

**Source:** ALiEM | **Author:** Michelle Lin, MD
**Date:** March 12, 2010 | **Category:** Endocrine-Metabolic, ALiEM Cards
**License:** CC BY-NC-ND 3.0
**URL:** https://www.aliem.com/paucis-verbis-hyperkalemia-management/

Hyperkalemia is a common presentation in the Emergency Department, especially in the setting
of acute renal failure...

## PV Card: Hyperkalemia

Adapted from [1]. Go to ALiEM (PV) Cards for more resources.

## References
1. Weisberg L. Management of severe hyperkalemia. Crit Care Med. 2008;36(12):3246-3251.
```

---

## Phase 3: Bulk Scraper (`aliem_bulk_scrape.py`)
Parallel scraper with resume support — identical pattern to REBEL EM and LITFL.

- Load discovery JSON
- **Track A mode:** `--track-a` flag to only scrape CC-licensed PV Cards + MEdIC
- **Track B mode:** `--track-b` for remaining posts (requires permission first)
- **Full mode:** default, scrapes everything
- Track progress in `output/metadata/bulk_scrape_log.json`
- Track errors in `output/metadata/bulk_scrape_errors.json`
- Default 3 workers with 5s delay
- Resume support (`--resume`)
- Retry failed pages (`--retry-errors`)
- Optional `--no-gcs` for local-only testing

### Estimated Time
- **Track A only:** ~200 posts × 5s delay = ~17 min with 1 worker, ~6 min with 3 workers
- **Full scrape:** ~2,500 posts × 5s delay = ~3.5 hours with 1 worker, ~1.2 hours with 3 workers

---

## Phase 4: Indexer (`aliem_indexer.py`)
Create a Vertex AI RAG corpus and index all markdown files — identical pattern to LITFL/REBEL EM indexer.

- **Corpus display name:** `aliem-foamed`
- **Corpus description:** "Emergency medicine education and clinical reference from ALiEM (aliem.com) — Paucis Verbis cards, clinical pearls, tricks of the trade, SAEM clinical images"
- **Embedding model:** `text-embedding-005`
- **Chunk size:** 1024, overlap 200 (same as all other corpora)
- **GCS bucket:** `clinical-assistant-457902-aliem`
- Upload markdown to `gs://clinical-assistant-457902-aliem/processed/{slug}.md`
- Upload metadata to `gs://clinical-assistant-457902-aliem/metadata/{slug}.json`
- Save corpus config to `aliem_rag_config.json`

### Estimated Indexing Time
- **Track A:** ~200 files × ~5s/file = ~17 min
- **Full:** ~2,500 files × ~5s/file = ~3.5 hours

---

## Phase 5: Backend Integration (`api/rag_service.py` + `api/main.py`)
Add ALiEM as a new source — same pattern as LITFL/REBEL EM.

### rag_service.py
```python
ALIEM_CORPUS_ID = os.environ.get("ALIEM_CORPUS_ID", "<new-corpus-id>")
ALIEM_BUCKET = f"{PROJECT_ID}-aliem"
# Add aliem_corpus_name to __init__
# Add "aliem" case to query_stream() corpus selection
# Add _get_aliem_metadata() method (same pattern as _get_litfl_metadata)
# Add _get_images_from_contexts() handler for aliem
```

### main.py
```python
# Update default sources:
sources: List[str] = Field(default=["local", "wikem", "pmc", "litfl", "rebelem", "aliem"])

# Add ALiEM citation handler in _build_citations():
if source_type == "aliem":
    slug = ... # extract from GCS path
    metadata = rag_service._get_aliem_metadata(slug)
    url = f"https://www.aliem.com/{slug}/"
    # Same pattern as LITFL citations
```

### Cloud Run env var
```
ALIEM_CORPUS_ID=<new-corpus-id>
```

---

## Phase 6: Frontend Integration (`frontend/app/page.tsx`)
Add ALiEM toggle to the Ed Universe sidebar.

- Download ALiEM logo → `frontend/public/logos/aliem-logo.png`
- Add state: `aliemEnabled`, `aliemExpanded`
- Add toggle UI block (after REBEL EM) with:
  - Blue checkbox color (`bg-blue-600 border-blue-600`) — ALiEM brand color
  - Logo image
  - "ALiEM" label
  - Count (dynamic based on track)
  - Expandable description: "Emergency medicine education from Academic Life in Emergency Medicine — PV Cards, clinical tricks, SAEM images, PEM pearls, and more."
- Add `"aliem"` to default sources array and save/load logic
- Add ALiEM citation rendering (blue badge, aliem.com links)

---

## File Structure
```
scrapers/aliem/
├── aliem_discovery.py        # Phase 1: Sitemap discovery
├── aliem_scraper.py          # Phase 2: Single-page scraper
├── aliem_bulk_scrape.py      # Phase 3: Parallel bulk scraper
├── aliem_indexer.py          # Phase 4: RAG corpus indexer
├── aliem_rag_config.json     # Auto-generated corpus config
├── requirements.txt          # Python dependencies
├── ALIEM_SCRAPER_PLAN.md     # This file
├── discovery/
│   └── aliem_discovery.json
└── output/
    ├── raw/                  # Raw HTML files
    ├── processed/            # Clean markdown + JSON
    └── metadata/             # Bulk scrape logs
```

---

## Execution Order
```bash
# 1. Discovery
cd scrapers/aliem
python3 aliem_discovery.py --sitemap

# 2. Test single PV Card page
python3 aliem_scraper.py --url "https://www.aliem.com/paucis-verbis-hyperkalemia-management/"

# 3. Track A: Scrape CC-licensed content only (~6 min)
python3 aliem_bulk_scrape.py --track-a --workers 3

# 4. Create corpus (one-time)
python3 aliem_indexer.py --create-corpus

# 5. Index Track A (~17 min)
python3 aliem_indexer.py --index-all --workers 1

# 6. Backend: add ALIEM_CORPUS_ID to rag_service.py + main.py
# 7. Deploy backend with new env var
# 8. Frontend: add ALiEM toggle + logo
# 9. Deploy frontend

# --- If permission granted for Track B ---
# 10. Scrape remaining posts
python3 aliem_bulk_scrape.py --track-b --workers 3 --resume

# 11. Index new files
python3 aliem_indexer.py --index-all --workers 1 --resume
```

---

## Risk Mitigation

### Legal
- **Track A (PV Cards + MEdIC):** CC BY-NC-ND 3.0 — same legal basis as REBEL EM ✅
- **Track B (all other content):** "All Rights Reserved" — requires explicit permission ⚠️
- **Attribution:** Every markdown file includes CC BY-NC-ND 3.0 attribution
- **No derivatives:** RAG retrieves and quotes original text with attribution, does not create derivative works
- **Non-commercial:** Educational/clinical tool, not monetized
- **robots.txt `ai-train=no`:** Our use is `ai-input` (retrieval-augmented generation), not model training. The `ai-input` signal is not specified, meaning ALiEM "neither grants nor restricts permission" for this use case.

### Technical
- **Cloudflare protection:** Conservative 5s delay, standard browser headers, retry with backoff
- **Jetpack CDN images:** Parse `i0.wp.com` URLs to get original image paths
- **Rate limiting:** If 429s encountered, exponential backoff up to 60s
- **JS challenges:** If Cloudflare serves challenges, may need to add `cloudscraper` library or reduce concurrency to 1 worker
- **No Crawl-delay:** robots.txt doesn't specify one, but we use 5s out of courtesy (Cloudflare sites are sensitive)

### Content Quality
- **PV Cards** are extremely high value — concise clinical reference cards covering hyperkalemia, RSI, ABG interpretation, septic arthritis, burn wounds, PE prediction rules, etc.
- **MEdIC Series** covers medical ethics cases — less clinical but valuable for teaching
- **Non-clinical content exists:** wellness posts, book clubs, match advice, conference recaps. The RAG retriever will rank clinical content higher for clinical queries naturally.
- **Consider category filtering** at discovery time to exclude clearly non-clinical categories (annual-report, sales, creative, life/wellness, clerkships, etc.)

---

## Next Steps
1. ✅ Create this plan document
2. ⏳ Build `aliem_discovery.py` — run sitemap discovery, tag URLs by track
3. ⏳ Build `aliem_scraper.py` — test on PV Card and clinical post
4. ⏳ Build `aliem_bulk_scrape.py` — run Track A first
5. ⏳ Contact ALiEM team re: permission for Track B content
6. ⏳ Build `aliem_indexer.py` and index Track A
7. ⏳ Backend + frontend integration
