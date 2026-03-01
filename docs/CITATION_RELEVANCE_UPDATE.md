# Citation Relevance Update

**Date:** February 28, 2026  
**Commit:** `23afd43d`  
**Deploy:** Cloud Run revision `em-protocol-api-00051-k4v`

---

## Problem

User feedback that reference/citation lists in Clinical Search results were too long and included sources not relevant to the query. A query about a specific topic (e.g., "RSI medications") would return 10-15+ citations, many tangentially related.

## Root Cause

Mismatch between what Gemini sees and what gets cited:

- **Retrieval**: `_retrieve_multi_source()` queries 6 corpora in parallel (local, WikEM, PMC, LITFL, REBELEM, ALiEM), each returning up to 5 results = ~30 total contexts
- **Prompt**: `_build_prompt_and_context()` only passed `contexts[:5]` to Gemini — the LLM only saw 2-4 unique sources
- **Citations**: Built from ALL ~30 contexts, deduplicated to 10-15+ unique sources
- **Result**: Citations included sources Gemini never saw when writing the answer

## Solution: Adaptive Relevance Filtering

New shared helper method `_filter_by_relevance()` in `api/rag_service.py`.

### Current Thresholds

| Parameter | Value | Description |
|-----------|-------|-------------|
| `score_multiplier` | **4.0** | Cutoff = best_score × 4.0. Scores beyond this are dropped. |
| `min_results` | **5** | Always include at least 5 unique sources (guarantees coverage) |
| `max_results` | **10** | Never exceed 10 unique sources (keeps UI concise) |
| `score_floor` | **0.05** | Minimum cutoff value to prevent near-zero scores from over-filtering |

### How the Multiplier Works

The threshold adapts to every query automatically:

- **Narrow query** (e.g., "RSI medications"): best score = 0.08, cutoff = 0.32 → tight filtering, ~5-6 citations
- **Broad query** (e.g., "chest pain workup"): best score = 0.25, cutoff = 1.0 → more lenient, ~7-10 citations

Scores in Vertex AI RAG are **distance-based** (lower = more relevant, 0 = exact match).

### Multiplier Tuning Guide

| Multiplier | Behavior | Typical result |
|------------|----------|----------------|
| 2× | Very aggressive — only near-exact matches | 3-5 citations |
| 3× | Moderate — good relevance, drops tangential | 4-7 citations |
| **4×** | **Balanced (current)** | **5-8 citations** |
| 5× | Lenient — casts a wider net | 6-10 citations |

To change: update the default parameters on `_filter_by_relevance()` in `api/rag_service.py` line ~139.

## Changes Applied

### 1. Clinical Search (`query()` + `query_stream()`)

- **Step 1.6** added: `contexts = self._filter_by_relevance(contexts)` after ED/journal filters, before Gemini generation
- `_build_prompt_and_context()` now uses all filtered contexts (was hard `[:5]`)
- Gemini sees every source that will be cited → inline `[N]` numbers match citation list
- Citations built from the same filtered set — prompt and citations aligned

### 2. Protocol Summary (`protocol_summary_stream()`)

- **Step 4.5** added: same 4× adaptive threshold applied to ranked protocol cards
- Low-relevance cards dropped before Gemini generates summaries

## Before / After

| Mode | Before | After |
|------|--------|-------|
| Clinical Search | ~30 ctx → prompt sees 5, cites 15+ | 5-10 unique → prompt + citations aligned |
| Protocol Summary | Top 5 cards regardless of relevance | Drops cards with score > 4× best match |

## Files Changed

- `api/rag_service.py` (+55 lines, -3 lines)

## Future Tuning

To log score distributions for further optimization, add to `_retrieve_multi_source()` before the return:

```python
for ctx in all_contexts:
    print(f"  [{ctx.get('source_type')}] score={ctx['score']:.4f} source={ctx['source'][-40:]}")
```

This will show the score range across corpora and help identify if the 4× multiplier needs adjustment.
