# RAG System Prompt Upgrade — February 17, 2026

## Changes Made

### 1. System Prompt Rewrite (`api/rag_service.py`)

**Old prompt** — generic "clinical assistant," weak format guidance, 1000 token limit.

**New prompt** — three major improvements:

| Area | Before | After |
|------|--------|-------|
| Persona | "emergency medicine clinical assistant" | "clinical decision support tool...actionable advice at the bedside" + local protocol support |
| BLUF | None | 🔴 **BOTTOM LINE:** 1-2 sentence actionable summary at top of every response |
| Structure | "Start with bold header, bullets" | Flexible per question type: tables for dosing/scoring, categorized lists for contraindications, numbered steps for procedures, protocol-native structure for local protocols |
| Tables | Not mentioned | Explicit instruction to use markdown tables for dosing, scoring tools, side-by-side comparisons |
| Warnings | Not mentioned | ⚠️ **WARNING** prefix for life-threatening pitfalls |
| Citations | "Add [1], [2]" | "Every factual claim should have a citation" (stronger requirement) |
| Length | maxOutputTokens: 1000 | maxOutputTokens: 2000 (room for tables, but instructed to be concise when possible) |

### 2. Frontend: GFM Table Support (`frontend/`)

- Installed `remark-gfm` package
- Added `remarkPlugins={[remarkGfm]}` to `<ReactMarkdown>` component
- Without this, markdown `| table | syntax |` renders as plain text

### 3. Frontend: Table CSS Styling (`frontend/app/globals.css`)

Added `.prose table` styles:
- Blue header border for visual hierarchy
- Proper cell padding and alignment
- Hover state on rows for scanability
- Full dark mode support (borders, text, hover states)

## Expected Impact

Based on Gemini comparison analysis (Gemini scored 9.2/10, RAG scored 3.6/10):

| Improvement | Expected Score Impact |
|-------------|----------------------|
| BLUF summary | +1.5 — instant actionable answer |
| Table formatting | +1.5 — dosing/scoring much more scannable |
| Categorized structure | +1.0 — contraindications, differentials organized |
| Warning emphasis | +0.5 — critical pitfalls stand out |
| Flexible length | +0.5 — complex queries get full treatment |

**Projected new score: ~7-8/10** (up from 3.6, with citation advantage over Gemini)

## To Test

1. Restart the API server
2. Re-run the same 5 comparison queries
3. Compare format quality against Gemini baselines in `docs/COMPLETE_GEMINI_RAG_COMPARISON.md`

## Files Changed

- `api/rag_service.py` — system prompt + maxOutputTokens
- `frontend/app/page.tsx` — remark-gfm import + plugin
- `frontend/app/globals.css` — table styles
- `frontend/package.json` — remark-gfm dependency
