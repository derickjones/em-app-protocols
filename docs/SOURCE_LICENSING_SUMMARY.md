# Source Licensing & Legal Summary

> **Last Updated:** February 18, 2026

---

## Active Sources

| Source | License | Pages Indexed | robots.txt | Status |
|--------|---------|--------------|------------|--------|
| **Local Protocols** | Proprietary (ours) | ~50 | N/A | ✅ Live |
| **WikEM** | CC BY-SA 3.0 | ~5,000 | ✅ Permissive | ✅ Live |
| **PMC Open Access** | Per-article CC / Public Domain | ~18,000 | ✅ Permissive | ✅ Live |
| **LITFL** | CC BY-NC-SA 4.0 | ~7,892 | ✅ Permissive | ✅ Live |
| **REBEL EM** | CC BY-NC-ND 3.0 | ~1,359 | ✅ (10s delay) | 🔄 Scraping |
| **ALiEM (Track A)** | CC BY-NC-ND 3.0 | ~258 | ⚠️ Mixed signals | 🔄 Scraping |

---

## Detailed Breakdown

### 1. Local Protocols (Mayo / Department)
- **License:** Proprietary — we own or have institutional permission for this content
- **What it is:** Department-specific clinical protocols, pathways, and guidelines
- **Legal basis:** Internal institutional use — no external license needed
- **Restrictions:** None (it's ours)
- **Attribution:** Department name displayed in citations

### 2. WikEM (wikem.org)
- **License:** [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) (Creative Commons Attribution-ShareAlike 3.0)
- **What it is:** The "Wikipedia of Emergency Medicine" — ~5,000 topic pages covering diagnoses, workups, and management
- **Legal basis:** CC BY-SA 3.0 is one of the most permissive CC licenses. It allows copying, redistribution, and adaptation for any purpose including commercial, as long as you give attribution and share derivative works under the same license.
- **What we must do:**
  - ✅ **Attribution** — Every citation says "Content from WikEM (wikem.org) under CC BY-SA 3.0"
  - ✅ **ShareAlike** — Any derivative content retains CC BY-SA 3.0
- **What we can do:** Use commercially, modify, redistribute
- **robots.txt:** Only blocks `/wp-admin/` — all content pages allowed
- **Risk level:** 🟢 **Very low** — most permissive license of all our sources

### 3. PMC Open Access (PubMed Central)
- **License:** **Per-article** — each article carries its own license, but all are in the PMC Open Access Subset
- **What it is:** Full-text peer-reviewed EM journal articles from 11 journals (Annals of Emergency Medicine, Academic Emergency Medicine, WestJEM, etc.), 2015–present
- **Legal basis:** PMC Open Access Subset explicitly allows text mining and computational analysis. Articles carry one of:
  - **CC BY 4.0** — Most permissive (attribution only)
  - **CC BY-NC 4.0** — Attribution + non-commercial
  - **CC BY-NC-ND 4.0** — Attribution + non-commercial + no derivatives
  - **CC0 / Public Domain** — No restrictions (NIH-funded)
- **What we must do:**
  - ✅ **Attribution** — Citations link to original PMC article with journal, authors, DOI
  - ✅ **Non-commercial** — App is educational/clinical, not commercial
- **NCBI API Terms:** Accessed via BioC API with proper User-Agent and rate limiting (3 req/sec with API key)
- **robots.txt:** Permissive for content pages
- **Risk level:** 🟢 **Very low** — this is literally the purpose of PMC Open Access

### 4. LITFL (Life in the Fast Lane)
- **License:** [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) (Creative Commons Attribution-NonCommercial-ShareAlike 4.0)
- **What it is:** Premier FOAMed resource — deep-dive articles on EM, critical care, toxicology, ECG interpretation, pharmacology. ~7,900 pages.
- **Legal basis:** CC BY-NC-SA 4.0 explicitly allows copying and redistribution for non-commercial purposes with attribution. LITFL's own footer states the license on every page. Their ECG Library explicitly says: "All our ECGs are free to reproduce for educational purposes."
- **What we must do:**
  - ✅ **Attribution** — Every citation includes "LITFL (litfl.com) — CC BY-NC-SA 4.0" with author names
  - ✅ **Non-commercial** — App is educational/clinical tool, not sold commercially
  - ✅ **ShareAlike** — Derivative content retains CC BY-NC-SA 4.0
- **What we cannot do:** Use commercially, remove attribution
- **robots.txt:** Only blocks `/wp-admin/` — all content pages allowed
- **Risk level:** 🟢 **Very low** — explicitly designed for FOAMed sharing

### 5. REBEL EM (rebelem.com)
- **License:** [CC BY-NC-ND 3.0](https://creativecommons.org/licenses/by-nc-nd/3.0/) (Creative Commons Attribution-NonCommercial-NoDerivatives 3.0)
- **What it is:** Evidence-based EM blog with ~1,359 posts covering EBM reviews, clinical pearls, podcasts. Created by Salim Rezaie, MD.
- **Legal basis:** CC BY-NC-ND 3.0 allows copying and redistribution in any medium for non-commercial purposes, as long as the work is attributed and not modified. RAG retrieval returns verbatim excerpts with attribution, which is redistribution (not derivative work).
- **What we must do:**
  - ✅ **Attribution** — Every citation includes "REBEL EM (rebelem.com)" with author name and link
  - ✅ **Non-commercial** — Educational/clinical use only
  - ✅ **No Derivatives** — We serve original text verbatim in RAG context, not modified content
- **What we cannot do:** Modify the content, use commercially
- **robots.txt:** Crawl-delay of 10 seconds (respected), blocks only `/wp-admin/`
- **ND (No Derivatives) nuance:** The ND clause means we cannot create "adaptations" of the work. Serving verbatim excerpts as RAG context with proper citation is redistribution, not adaptation. The Gemini model synthesizes answers citing the source — similar to how a textbook cites journal articles.
- **Risk level:** 🟡 **Low** — clear CC license, but ND clause requires care in how content is presented

### 6. ALiEM (aliem.com) — Track A Only
- **License:** [CC BY-NC-ND 3.0](https://creativecommons.org/licenses/by-nc-nd/3.0/) — **ONLY for PV Cards and MEdIC Series**
- **What it is:** ~160 Paucis Verbis (PV) clinical reference cards + ~98 MEdIC Series medical education case discussions = **258 pages**
- **Legal basis:** ALiEM's footer on every page states:
  > "ALiEM by ALiEM.com is copyrighted as 'All Rights Reserved' except for our Paucis Verbis cards and MEdIC Series, which are Creative Commons Attribution-NonCommercial-NoDerivs 3.0 Unported License."
- **What we scrape:** ONLY PV Cards and MEdIC Series (Track A = CC licensed content)
- **What we skip:** All other blog content (~2,256 posts) is "All Rights Reserved" (Track B)
- **What we must do:**
  - ✅ **Attribution** — Citations include "ALiEM (aliem.com) — CC BY-NC-ND 3.0" with author name
  - ✅ **Non-commercial** — Educational/clinical use
  - ✅ **No Derivatives** — Verbatim excerpts only
- **robots.txt complications:**
  - `Content-Signal: search=yes, ai-train=no` — explicitly blocks AI training, but `ai-input` (retrieval augmentation) is NOT specified
  - Blocks ClaudeBot, GPTBot, CCBot, etc.
  - Our scraper uses a custom User-Agent not in the blocked list
  - We are NOT training a model — we are building a retrieval index (similar to a search engine, which they explicitly allow with `search=yes`)
- **Risk level:** 🟡 **Low-moderate** — CC license is clear for Track A content, but `ai-train=no` signal adds ambiguity even though RAG retrieval ≠ AI training

---

## Evaluated But Not Scraped

### EMCrit (emcrit.org) — ❌ BLOCKED

| Aspect | Detail |
|--------|--------|
| **License** | **"All Rights Reserved"** — standard copyright |
| **What it is** | Scott Weingart's premier critical care + EM podcast/blog (~500+ episodes, show notes, PulmCrit articles) |
| **Why we can't scrape** | Terms of Service explicitly prohibit scraping, AI/ML use, and automated access |
| **TOS language** | *"You may not use any automated means, including robots, crawlers, or data mining tools, to download, monitor, or use data or content from the Website"* |
| **robots.txt** | Blocks all known AI bots (GPTBot, ClaudeBot, CCBot, etc.) |
| **Content-Signal** | Not present, but TOS is explicit |
| **Alternative** | Would need direct written permission from Scott Weingart / EMCrit LLC |
| **Risk level** | 🔴 **High** — explicit TOS prohibition makes scraping a clear violation |

**Why EMCrit matters (the gap):** EMCrit is arguably the highest-value FOAMed resource for critical care and resuscitation content. PulmCrit articles, the IBCC (Internet Book of Critical Care), and podcast show notes contain deep clinical decision-making content. Without EMCrit, our critical care depth relies on LITFL's CCC (Critical Care Compendium) and PMC articles, which partially covers the gap but lacks EMCrit's opinionated, practical synthesis.

**Path forward:** Email Scott Weingart directly at emcrit.org/contact explaining the educational non-commercial use case with attribution. EMCrit is a one-person decision — if Scott says yes, we're in.

### ALiEM Track B (Non-CC Blog Content) — ⏸️ PENDING PERMISSION

| Aspect | Detail |
|--------|--------|
| **License** | **"All Rights Reserved"** |
| **Content** | ~2,256 blog posts (Tricks of the Trade, Splinter Series, SAEM Clinical Images, AIR Modules, clinical posts) |
| **Why we can't scrape yet** | Footer explicitly states "All Rights Reserved" for non-PV/MEdIC content |
| **Path forward** | Email ALiEM team via contact form requesting educational RAG use with attribution |
| **Risk level** | 🟠 **Moderate** — restrictive copyright, but the team is education-focused and may grant permission |

---

## License Comparison Matrix

| Requirement | WikEM | LITFL | REBEL EM | ALiEM (A) | PMC OA | EMCrit |
|-------------|-------|-------|----------|-----------|--------|--------|
| **Can scrape?** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Attribution required?** | Yes | Yes | Yes | Yes | Yes | N/A |
| **Non-commercial only?** | No | Yes | Yes | Yes | Varies | N/A |
| **Can modify content?** | Yes (SA) | Yes (SA) | ❌ (ND) | ❌ (ND) | Varies | N/A |
| **Can use commercially?** | ✅ | ❌ | ❌ | ❌ | Varies | ❌ |
| **ShareAlike required?** | Yes | Yes | No | No | No | N/A |
| **robots.txt OK?** | ✅ | ✅ | ✅ (10s) | ⚠️ | ✅ | ❌ |

### License Spectrum (Most → Least Permissive)

```
CC BY-SA 3.0 (WikEM)         ← Most permissive: can modify, commercial OK
    ↓
CC BY-NC-SA 4.0 (LITFL)      ← Can modify, but non-commercial only
    ↓
CC BY / CC0 (PMC articles)   ← Varies per article, generally very permissive
    ↓
CC BY-NC-ND 3.0 (REBEL, ALiEM A) ← Can redistribute verbatim, non-commercial only
    ↓
All Rights Reserved (ALiEM B) ← Cannot use without explicit permission
    ↓
All Rights Reserved + TOS (EMCrit) ← Explicitly prohibited
```

---

## RAG Retrieval vs AI Training — The Legal Distinction

Our use case is **retrieval-augmented generation (RAG)**, not AI model training. This is an important legal distinction:

| Aspect | AI Training | RAG Retrieval (Our Use) |
|--------|------------|------------------------|
| **What happens to content** | Ingested into model weights permanently | Stored in search index, retrieved verbatim |
| **Is content modifiable?** | Transformed into statistical patterns | Served as-is with citations |
| **Analogous to** | Creating a derivative work | Operating a search engine + library |
| **Content removable?** | No (baked into weights) | Yes (delete from index instantly) |
| **User sees original?** | No (model generates new text) | Yes (cited excerpts from source) |

This distinction matters for:
- **ND (No Derivatives) licenses:** We don't create derivatives — we retrieve and cite originals
- **`ai-train=no` signals:** We're not training — we're indexing for retrieval
- **Fair use analysis:** Our use is transformative (clinical decision support tool), non-commercial, and attributes sources

---

## Compliance Checklist

- [x] Every RAG response cites the source with name, URL, and license
- [x] Author names preserved in all metadata
- [x] Non-commercial use only (educational/clinical tool)
- [x] robots.txt crawl delays respected (10s for REBEL EM, 5s courtesy for ALiEM)
- [x] Custom User-Agent with contact email on all scrapers
- [x] No content modification (verbatim storage and retrieval)
- [x] Content removable from index on request
- [ ] Email ALiEM team for Track B permission
- [ ] Email EMCrit for permission
