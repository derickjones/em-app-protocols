# Recommendation: Sub-6s Answers, Protocol Routing, Google Search & X Integration

**Date:** 2026-07-16  
**Status:** Recommendation (research + codebase analysis)  
**Goal:** Reduce perceived answer time from ~18s → **4–6s**, keep clinical depth and trustworthy citations, and evaluate Google AI Search + X/Twitter as product features.

---

## 1. Executive summary

| Area | Recommendation | Impact on 4–6s goal |
|------|----------------|---------------------|
| **Latency** | Route aggressively, shrink retrieval + prompt, stream first tokens earlier, parallelize post-work | **Primary path to 4–6s** |
| **“protocol” keyword** | Keep + tighten existing `route_query`; UI feedback when local-only | Already partially built; finish the product loop |
| **Depth / citations** | Tiered modes (Fast / Balanced / Deep) with hard caps (≈3–8 cites) | Prevents “more sources = slower + noisier” |
| **Google AI Search grounding** | **Optional supplement only**, never default for protocol care | Improves recency; **adds** latency/cost if always on |
| **X / Twitter** | **Curated FOAMed feed** via X API (or hosted MCP for tooling); not on the hot answer path | Engagement / awareness; do not put in critical latency path |

**Bottom line:** You do not need Google Search or X to hit 4–6s. You need a **faster default path** over the corpora you already own, with **smarter routing** when the user says “protocol.” Google Search and X are valuable **adjacent** capabilities.

---

## 2. How the app answers today (as implemented)

### 2.1 Hot path (Clinical Search)

```
Frontend page.tsx
  ├─ POST /query  (SSE stream)          ← blocks first tokens of answer
  └─ POST /protocol-summary (SSE)       ← fusion cards; non-blocking for text
        │
        ▼
api/main.py
  route_query(query)  → may force sources=["local"] or ["personal"]
        │
        ▼
rag_service.query_stream()
  1. _retrieve_multi_source()   # up to 6–7 Vertex RAG corpora in parallel, top_k=5 each
  2. PMC journal + ED/bundle path filters
  3. _allocate_slots(max_total=15)   # local/personal/foam/literature mix
  4. Gemini 2.5 Flash streamGenerateContent
       - prompt includes up to ~15 chunks × 4000 chars
       - maxOutputTokens = 8192
  5. _get_images_from_contexts()    # sequential GCS metadata lookups per citation
  6. SSE "done" with citations + images + query_time_ms
```

**Model:** `gemini-2.5-flash` (Vertex `us-central1`)  
**Retrieval:** Vertex AI RAG Engine `retrieveContexts` per corpus (`us-west4`)  
**Default frontend sources (when toggles on):** local + WikEM + PMC + LITFL + REBEL EM + ALiEM (+ personal)

### 2.2 Protocol keyword routing (already exists)

`api/query_router.py` already maps intent:

| Route | Trigger examples | Effective sources |
|-------|------------------|-------------------|
| `local_protocol` | any query containing **“protocol”**; also policy/guideline/pathway + local context (“our ED”, “Mayo”, …) | **`["local"]` only** |
| `personal` | “my file”, “uploaded PDF”, etc. | **`["personal"]` only** |
| `general_clinical` | everything else | user-selected sources (often all FOAM + PMC) |

So “protocol” already **tunes to local protocols**. Gaps are product/UX and edge cases (see §4), not a missing classifier.

### 2.3 Why ~18s is plausible

Rough wall-clock budget for a full multi-source query (order-of-magnitude; log `[rag-timing]` / `query_time_ms` to confirm):

| Stage | Typical range | Notes |
|-------|---------------|--------|
| Auth + cold start (Cloud Run) | 0–2s | Intermittent |
| OAuth token refresh (`credentials.refresh` every call) | 0.1–0.5s | Easy win |
| Parallel RAG retrieve (6 corpora) | **2–8s** | Wall time ≈ slowest corpus; timeout allows 30s |
| Prompt build + Gemini TTFT | **3–10s** | Large context + long system prompt |
| Streaming remainder | 2–8s | Driven by answer length; `maxOutputTokens=8192` invites long answers |
| GCS metadata for images (serial) | **1–4s** | Happens *after* stream, delays citations/images/`query_time_ms` |
| Fusion: `/protocol-summary` | 5–20s extra | Separate local retrieve + **1 Gemini call per protocol card** (up to 5, sequential) |

User-perceived “time to answer” is usually **time to first useful text** + time until they stop reading. Today, first tokens wait on full multi-corpus retrieval; total “done” waits on images + long generation.

**Fusion mode** (`/query` + `/protocol-summary` in parallel) does not block the answer stream, but doubles RAG + Gemini load on the same service and can steal capacity under load.

---

## 3. Target latency model (4–6s)

Define two product metrics:

| Metric | Target | Definition |
|--------|--------|------------|
| **TTFT** (time to first token) | **≤ 2.5s** p50 / **≤ 4s** p95 | User sees answer text streaming |
| **Useful answer complete** | **4–6s** p50 | Bottom line + main body done (citations/images may lag) |
| **Full done event** | ≤ 8s p50 | Citations + images + analytics |

Split the pipeline into **critical path** (must finish before tokens) vs **background** (images, cards, web, X).

```
Critical path (target ≤ 4s):
  route → retrieve (1–3 corpora) → compact context → stream Gemini

Background (do not block TTFT):
  images, protocol cards, Google Search (if any), X feed, analytics
```

---

## 4. Protocol keyword & local-protocol tuning

### 4.1 What works today

- Bare word **“protocol”** → `local_protocol` → sources forced to `local` only (faster + institution-first).
- Related terms: policy, guideline, pathway, order set, bundle, workflow, algorithm — with local context phrases.

### 4.2 Recommended product behavior

1. **Always honor explicit local intent**  
   - Keep: “protocol”, “our protocol”, “hospital guideline”, “per Mayo”, “order set”, etc.  
   - Return `route` in the UI (you already stream `route` on `done`) — show a chip: *“Searching local protocols only.”*

2. **Soft local boost for borderline queries**  
   - e.g. “sepsis bundle” without “protocol” → still multi-source, but **slot-allocate more local** (raise local weight in `_allocate_slots`) rather than dropping FOAM entirely.

3. **Fallback when local is empty**  
   - If `local_protocol` route returns zero contexts, auto-retry once with FOAM (wikem + litfl) and label the answer: *“No local protocol match — showing general ED sources.”*  
   - Avoids silent dead ends without defaulting every query to 6 corpora.

4. **Do not expand “protocol” to web search**  
   - Local PDF/corpus is the source of truth for institutional care. Google Search must never override local protocol text (aligns with existing prompt rule #5).

5. **Optional UI affordance**  
   - Toggle or mode: **“Local protocols”** vs **“Clinical search”** so users don’t rely only on keywords.

### 4.3 Edge cases to test

| Query | Expected route |
|-------|----------------|
| “sepsis protocol” | local_protocol |
| “what’s our RSI protocol” | local_protocol |
| “RSI medications” | general_clinical |
| “my uploaded hyperkalemia notes” | personal |
| “protocol for croup per AAP” | local_protocol today (because “protocol”) — may need **exception list** if users mean national guidelines |

**Recommendation:** if query contains both “protocol” and strong external markers (`AAP`, `ACEP`, `NICE`, `UpToDate`, `AHA`), prefer general_clinical or dual-source (local + literature) rather than local-only.

---

## 5. Balancing depth, speed, and citation count

### 5.1 Current defaults (problem)

| Knob | Current | Effect |
|------|---------|--------|
| Corpora per general query | up to 6–7 | Slowest corpus dominates TTFT |
| `top_k` per corpus | 5 | Up to ~30 raw chunks before slots |
| Slot allocator `max_total` | **15** | Large prompt |
| Chars per chunk in prompt | 4000 | Token bloat |
| Citation list | all allocated contexts | Often 8–15 items in UI |
| `maxOutputTokens` | **8192** | Long bedside answers |

More sources improve coverage only up to a point; past ~5–8 unique documents, physicians get noise and the model gets slower.

### 5.2 Recommended tiered modes

Expose three modes (backend enum + frontend control; default = **Balanced**):

| Mode | Corpora | top_k / corpus | Max slots | Max unique cites | maxOutputTokens | Target TTFT |
|------|---------|----------------|-----------|------------------|-----------------|-------------|
| **Fast** | local (if any) + 1 FOAM (wikem *or* litfl) | 3 | 6 | **3–5** | 1024–1536 | ~2–3s |
| **Balanced (default)** | local + wikem + litfl + (pmc if journal filter on) | 3–4 | **8** | **5–7** | 2048 | ~3–5s |
| **Deep** | all selected sources | 5 | 12–15 | **8–10** | 4096 | ~6–12s |

**Citation policy (all modes):**

- Cite only sources present in the prompt (already the right design).
- Cap unique sources: **min 3 / max 7** for Balanced; drop by relevance score (you previously used a 4× distance multiplier — reintroduce `_filter_by_relevance` *after* slot allocation or replace slots with score-based caps).
- Prefer **one chunk per FOAM/PMC article**; allow up to **2–3 chunks** for local protocols (already in allocator).

### 5.3 Depth without bloat

Keep the strong prompt structure you already have (Bottom Line, tables, stepwise procedures) but:

1. Cut total answer target from “under 1500 words” to **“under ~400 words unless Deep mode.”**
2. Put extended differential / rare edge cases behind “Expand” only if you add a follow-up call later.
3. Prefer **actionable structure over exhaustive literature review** for bedside use.

---

## 6. Latency playbook (priority-ordered)

### P0 — Highest ROI (should get you into the 4–6s band)

| # | Change | Where | Why |
|---|--------|-------|-----|
| 1 | **Default to Balanced corpus set** (not all 6 FOAM sources) | frontend defaults + API defaults | Cuts slowest-of-N retrieval |
| 2 | **Lower `top_k` 5 → 3** on general path | `rag_service._retrieve_multi_source` | Less ranking + less noise |
| 3 | **`max_total` slots 15 → 8** | `_allocate_slots` | Smaller prompt → faster TTFT |
| 4 | **Chunk truncate 4000 → 1500–2000** | `_build_prompt_and_context` | Token reduction |
| 5 | **`maxOutputTokens` 8192 → 2048** (Balanced) | `generate_answer_stream` | Shorter answers complete sooner |
| 6 | **Stream citations/images after text** | already mostly true; ensure UI doesn’t wait on `done` for first paint | Perceived speed |
| 7 | **Cache OAuth access tokens** until expiry | `_get_access_token` | Avoid refresh per request |

### P1 — Strong improvements

| # | Change | Notes |
|---|--------|-------|
| 8 | **Adaptive retrieval timeouts** | Fail slow corpus at 2.5–3s; continue with partial results |
| 9 | **Prefetch / warm metadata cache** for top protocols | Or embed image URLs in retrieval metadata to skip GCS on hot path |
| 10 | **Parallelize GCS metadata** with `ThreadPoolExecutor` | Cuts post-stream lag |
| 11 | **Protocol-summary: batch summaries** or template without Gemini when score is strong | Today: up to **5 sequential Gemini calls** per query in fusion mode |
| 12 | **Region co-location** | RAG is `us-west4`, Gemini is `us-central1` — consider co-locating generation with retrieval or using global endpoint where appropriate |
| 13 | **Reuse local retrieve** between `/query` and `/protocol-summary`** | Single retrieve → dual consumers, or skip cards when route is general_clinical |

### P2 — Architecture upgrades (if P0/P1 insufficient)

| # | Change | Notes |
|---|--------|-------|
| 14 | Hybrid search (BM25 + vector) on local protocols | Faster exact protocol title hits |
| 15 | Smaller / faster model for Fast mode (`gemini-2.5-flash-lite` or future Flash-Lite) | Trade some prose quality |
| 16 | Vertex AI Search engine over RAG Engine for multi-corpus | Managed retrieval quality; measure latency separately |
| 17 | Speculative dual-path: Fast answer + background Deep enrichment | Advanced UX |

### Instrumentation (do this first)

Add structured timing to every query log:

```
route, sources[], retrieve_ms_by_corpus{}, allocate_ms, gemini_ttft_ms,
gemini_total_ms, image_ms, total_ms, slot_counts{}, citation_count
```

Without this, optimization is guesswork. You already partially log `[rag-timing]` and `query_time_ms`.

---

## 7. Google AI Search / Grounding with Google Search

### 7.1 What it is

Google’s product is **Grounding with Google Search** (Gemini tool `google_search` / Vertex `GoogleSearch`), not a separate “Google AI Search” brand for this use case. The model decides when to search the public web, synthesizes an answer, and returns grounding metadata (URLs, supports, Search Suggestions).

Sources researched:

- [Gemini API — Grounding with Google Search](https://ai.google.dev/gemini-api/docs/google-search)
- [Vertex / Gemini Enterprise — Grounding with Google Search](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/grounding/grounding-with-google-search)
- Industry guidance: healthcare/finance often need **only provided context**, not open web (Google Cloud RAG/grounding materials)

### 7.2 Would it make answers faster?

**No — not as a default.** Search grounding adds:

1. Query planning  
2. One or more web searches (each billable on Gemini 3-class models)  
3. Extra synthesis  

Typical grounded calls are **slower** than pure RAG-over-your-index. Community reports also note variable web-search latency.

**Cost (order of magnitude):** historically ~**$35 per 1,000 grounded prompts** (verify current Vertex SKU; Gemini 3 bills **per search query issued**, not always per user prompt).

### 7.3 Would it make answers better?

| Use case | Helpful? | Risk |
|----------|----------|------|
| Local protocol questions | **No** | Wrong institution, outdated public PDFs |
| Classic EM (RSI, hyper-K, sepsis) | Marginal | Your FOAM corpora already cover this with better attribution |
| **Recency** (drug shortages, new FDA labels, outbreak, “new ACEP guideline 2026”) | **Yes** | Must label as web / non-institutional |
| Rare diseases / obscure tox | Sometimes | Quality varies; still not peer-review filtered like PMC corpus |
| Images / media from web | Possible (Image Search preview) | Attribution & licensing complexity |

Google’s own positioning: grounding helps **accuracy + freshness**; industries with strict source control should ground on **their** data. That is your RAG corpus.

### 7.4 Recommended integration design

**Do not replace RAG.** Add an **optional “Web” source** or automatic trigger.

```
if route == local_protocol:
    RAG local only  # never Google Search on critical path

elif query needs recency OR user enabled "Web":
    Path A (preferred for speed): existing multi-source RAG first (stream)
    Path B (async): optional Google Search enrichment as secondary panel
       OR second-pass only if RAG confidence low

elif Deep mode + web enabled:
    Gemini call with tools=[google_search] AFTER or INSTEAD of FOAM
    Map grounding_chunks → citation UI (separate badge: "Web")
```

**API sketch (Vertex-style):**

```python
# Optional second tool call — not default
config = GenerateContentConfig(
    tools=[Tool(google_search=GoogleSearch(
        # optional: exclude_domains=["reddit.com", "quora.com"]
    ))],
    # temperature often higher for search tools per Google guidance
)
```

**UI requirements if you enable Google Search Suggestions:**  
Google’s terms require displaying Search Suggestion chips / entry points in a compliant way when returned — plan frontend work before flipping the switch in production.

**Clinical safety rules:**

1. Web never overrides Local Protocol or User Upload.  
2. Distinct citation style (e.g. grey “Web” vs blue “Local”).  
3. Disclaimer: “Web results are not your institutional protocol.”  
4. Prefer domain allowlist for Deep mode later (e.g. `acep.org`, `nih.gov`, `cdc.gov`, `who.int`) if Vertex tooling supports exclude/include patterns adequately.

### 7.5 Decision

| Question | Answer |
|----------|--------|
| Help hit 4–6s? | **No** |
| Worth building? | **Yes, as opt-in “Web” / recency layer** after Fast path is solid |
| Priority | **P2 product**, after P0 latency work |

---

## 8. X (Twitter) MCP & FOAMed accounts in the product

### 8.1 What “X MCP” is

As of mid-2026, X provides a **hosted MCP server** at `https://api.x.com/mcp` for AI tools (Cursor, Claude, Grok Build, etc.), typically via the `xurl` OAuth bridge or app-only Bearer. It exposes search, user lookup, timelines, trends, etc.

Docs: [X MCP servers](https://docs.x.com/tools/mcp)

**Important distinction:**

| Layer | Good for |
|-------|----------|
| **MCP** | Developer agents, internal tooling, ops assistants |
| **Product backend (your FastAPI app)** | End-user features in EM Protocols iOS/web |

MCP is **not** the ideal way to serve every physician’s phone. Your API should call the **X API v2** (or a small service) with **app credentials**, not each user’s MCP session. Use MCP for *your* engineering workflow; use the API for the product.

### 8.2 Product value for emergency medicine

Curated FOAMed signal is real:

- Guideline drops, conference pearls, ECG cases, airway tips  
- Accounts clinicians already follow (examples to curate — verify handles before shipping):  
  LITFL / FOAMed educators, EMCrit-adjacent voices, journal accounts, ACEP/SAEM, toxicology educators, ultrasound FOAMed, etc.

**Do not** put live X fetch on the **answer critical path**. Social posts are unvetted and high-variance for dosing/protocols.

### 8.3 Recommended product features

#### A. “EM Pulse” feed (primary)

1. Maintainer-curated list of **~30–80** noteworthy EM accounts (Firestore collection `em_x_accounts`).  
2. Backend cron (Cloud Scheduler → Cloud Run job) every 15–60 min:  
   - Pull latest posts via X API user timeline / filtered stream / recent search  
   - Store in Firestore/BigQuery with: author, text, media URLs, created_at, topics tags  
3. Frontend tab or drawer: chronological + topic filters (airway, cardio, peds, tox…).  
4. Optional: “Open on X” deep links only.

#### B. Optional answer enrichment (secondary, never default)

- If user enables **“Include FOAMed social”** *or* Deep mode:  
  - Keyword search over **your indexed posts** (not live MCP) for last 30–90 days  
  - Show as a **sidebar panel**: “Recent discussion” — not mixed into protocol dosing  
- Explicit disclaimer: opinion / educational social media, not protocol.

#### C. Admin curation

- Super-admin UI to add/remove handles, mute accounts, pin topics.  
- Auto-tag with a cheap classifier (Gemini Flash-Lite) offline.

### 8.4 Integration options compared

| Approach | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| **Hosted X MCP in physician app** | Fast prototype for agentic UX | Auth model is per-developer/tool; rate limits; not multi-tenant friendly | ❌ Not for end users |
| **X API v2 in your backend** | Correct multi-tenant product architecture | Need X developer app + pay-per-use; rate limits | ✅ **Yes** |
| **Third-party Twitter data MCP/APIs** | Sometimes cheaper scraping wrappers | ToS/reliability risk for clinical product | ⚠️ Research carefully |
| **Manual RSS / blog mirrors** | Stable | Misses real-time X discourse | Supplement only |

### 8.5 Compliance / risk notes

- X API terms, automated account labeling, and rate limits apply.  
- Do **not** auto-like/follow.  
- PHI: never post clinical cases from the app to X.  
- Content moderation: FOAMed can be wrong; UI must not look like “cited evidence” equal to PMC/local protocol.  
- Store minimal data; honor account deletion / takedowns.

### 8.6 Suggested phased rollout

1. **Week 1–2:** Curated list + nightly pull + read-only feed UI (no RAG coupling).  
2. **Later:** Topic tags + search over stored posts.  
3. **Optional:** Deep-mode “related FOAMed posts” panel.  
4. **Internal only:** connect X MCP to Grok/Cursor for ops (monitoring hashtags, finding new educators).

---

## 9. Target architecture (after recommendations)

```
                    ┌─────────────────────────────┐
  User query ──────►│ route_query + mode (F/B/D)  │
                    └─────────────┬───────────────┘
                                  │
           ┌──────────────────────┼──────────────────────┐
           ▼                      ▼                      ▼
    local_protocol         general Fast/Balanced      personal
    retrieve local         1–3 corpora, k=3           personal corpus
           │                      │                      │
           └──────────┬───────────┴──────────┬───────────┘
                      ▼                      │
              slot ≤8, cite ≤7               │
              Gemini stream (TTFT)           │
                      │                      │
         ┌────────────┼────────────┐         │
         ▼            ▼            ▼         │
      answer      images async   protocol    │
      (4–6s)      + citations    cards       │
                                  │
         Optional (off critical path):
         • Google Search panel (recency / Web toggle)
         • EM Pulse X feed (pre-indexed)
```

---

## 10. Implementation roadmap

### Phase 0 — Measure (1–2 days)

- [ ] Log per-stage timings to Cloud Logging + analytics  
- [ ] Capture p50/p95 for 20 representative queries (protocol vs general)  
- [ ] Confirm whether 18s is TTFT, total stream, or full `done` with images

### Phase 1 — Fast path (3–7 days) → **primary path to 4–6s**

- [ ] Defaults: Balanced sources (local + wikem + litfl; PMC opt-in)  
- [ ] top_k=3, max slots=8, chunk=2000, maxOutputTokens=2048  
- [ ] Token cache; parallel metadata; retrieval timeout 3s  
- [ ] UI chip for `route`  
- [ ] Empty-local fallback  

**Success criteria:** p50 TTFT ≤ 2.5s; p50 useful answer ≤ 6s on Balanced mode with warm Cloud Run.

### Phase 2 — Protocol UX + fusion efficiency (3–5 days)

- [ ] External-guideline exception for “protocol + AAP/ACEP…”  
- [ ] Soft local boost for general_clinical  
- [ ] Protocol-summary: share retrieve with query or skip Gemini when not needed  
- [ ] Citation hard cap 5–7 with score filter  

### Phase 3 — Google Search (optional, 1–2 weeks)

- [ ] Feature flag `WEB_SEARCH_ENABLED`  
- [ ] Opt-in source toggle “Web”  
- [ ] Map grounding metadata → citations + required Search Suggestions UI  
- [ ] Never on `local_protocol` route  

### Phase 4 — X FOAMed feed (1–3 weeks)

- [ ] X developer app + backend poller  
- [ ] Curated account list + Firestore store  
- [ ] Read-only feed in app  
- [ ] (Later) related posts panel for Deep mode  

---

## 11. Success metrics

| Metric | Baseline (est.) | Target |
|--------|-----------------|--------|
| Answer TTFT p50 | ~8–15s? | **≤ 2.5s** |
| Useful answer p50 | ~18s | **4–6s** |
| Citations shown (Balanced) | often 10–15 | **5–7** |
| Local protocol hit rate when “protocol” used | measure | ≥ 80% non-empty |
| Web search attach rate | 0% | < 15% of queries if enabled |
| X feed DAU engagement | n/a | optional KPI later |

---

## 12. Explicit non-goals (keep the system simple)

- Do **not** run Google Search on every query “for quality.”  
- Do **not** mix unvetted tweets into dosing guidance.  
- Do **not** add agentic multi-hop tools before the Fast path is solid.  
- Do **not** raise slot counts or max tokens without re-measuring latency.

---

## 13. Summary recommendation

1. **Speed:** Treat multi-corpus retrieval + oversized prompts + long generation as the main 18s problem. Ship **Balanced mode defaults**, lower top_k/slots/tokens, cache auth, time out slow corpora, and keep images/cards off the critical path.  
2. **Protocols:** Keyword routing already exists — finish UX (chips, fallback, guideline exceptions) rather than rebuilding intent detection.  
3. **Citations:** Cap at **5–7** high-relevance sources in default mode; align prompt and cite list.  
4. **Google Search grounding:** Valuable for **recency**, not for latency or local protocols. Integrate as **opt-in Web**, post- or side-channel.  
5. **X:** Build a **curated FOAMed feed** with the X API in your backend; use official X MCP for internal AI tooling, not as the patient-care answer path.

---

## Appendix A — Key code map

| Concern | File |
|---------|------|
| Query API + routing apply | `api/main.py` (`/query`, `/protocol-summary`) |
| Intent routing | `api/query_router.py` |
| Multi-corpus retrieve, slots, Gemini, images | `api/rag_service.py` |
| Frontend sources + fusion | `frontend/app/page.tsx` |
| Prior citation filtering notes | `docs/CITATION_RELEVANCE_UPDATE.md` |
| Gemini format learnings | `docs/GEMINI_PATTERN_ANALYSIS.md` |

## Appendix B — Example latency experiment matrix

Run the same 10 questions under:

1. Current production defaults  
2. local only  
3. local + wikem  
4. Balanced (local + wikem + litfl)  
5. Full FOAM + PMC  

Record TTFT and total_ms. Choose the cheapest configuration that still passes clinical quality review for default mode.

---

*End of recommendation document.*
