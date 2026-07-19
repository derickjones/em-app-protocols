# PMC Sharding Workstream

**Status:** Ready to implement
**Owner:** (assign)
**Tracking:** Linear EMA-97 (Experiment 9 = root cause; this doc = the fix)
**Prereq reading:** `docs/SPEED_AND_SOURCE_STRATEGY.md`

This is a self-contained implementation spec. It assumes no prior context. Follow
the phases in order; each has explicit, verifiable **Success Criteria** — do not
advance a phase until its criteria pass.

---

## 1. Problem & goal

PMC retrieval takes ~9-10s; every other corpus takes <1-2s. Root cause is
**confirmed and documented, not inferred**: the PMC RAG corpus has **56,156 files**,
~5.6x past Google's stated **10,000-file threshold** for the default exact-KNN
vector backend (`ragManagedDb` + `knn`) that all corpora use. Per Google's docs,
KNN "is good for corpora under 10,000 files"; past that, latency climbs with size.
LITFL (7,892 files, same backend) retrieves in ~0.6-1.5s — proof that a corpus in
that size range is fast on KNN.

An ANN (Vector Search 2.0) migration was investigated and **rejected**: ANN is only
in `us-central1`, and creating a corpus there requires switching the whole project
to Serverless mode — a project-wide change with undocumented effect on the 6
existing `us-west4` corpora. Too risky.

**Goal:** split PMC into multiple smaller KNN corpora ("shards"), each kept **below
10,000 files with a safety margin (target ≤7,500)**, all remaining in `us-west4` on
the same proven backend. PMC retrieval then becomes ~9 fast parallel calls instead
of one slow call. **The design must be scalable** — future journal/content
additions must follow the same pattern with minimal effort — **and must connect
cleanly to the existing frontend journal selection.**

### Success definition for the whole workstream
1. PMC retrieval contribution to `/query` drops from ~10s to ~1-2s.
2. No loss of content (sharded total file count == original 56,156) or citation/
   journal-filter behavior.
3. Adding new PMC content later requires only re-running the shard tool + a deploy —
   no hand-editing of shard assignments in app code.
4. Frontend journal selection drives which shards are queried (deselected journals'
   shards are skipped) and remains correct for any selection.

---

## 2. Three-layer model (read this before coding)

Keep these distinct — conflating them is the main way this goes wrong:

- **Shard** — physical unit. One Vertex RAG corpus, KNN, `us-west4`, capped at
  **≤7,500 files** (target; 10,000 is the hard limit). ~9 shards total.
- **Journal** — logical unit the user selects (37 journals today). A journal lives
  in exactly one shard, *except* a journal larger than the cap, which is split
  across consecutive shards (only "JAMA Netw Open" at 9,943 today).
- **UI group** — display grouping (4 today). Shards never span UI groups, so
  selecting a group maps to a small, contiguous set of shards.

**Bridge between them: the shard registry** (`scrapers/PMC/pmc_shard_registry.json`,
created in Phase 1). Single source of truth. Shape:
```json
{
  "target_cap": 7500,
  "reshard_watermark": 8500,
  "location": "us-west4",
  "embedding_model": "text-embedding-005",
  "chunk_size": 1024,
  "chunk_overlap": 200,
  "shards": [
    {"id": "shard_00", "corpus_id": "<filled in Phase 2>", "file_count": 6928,
     "ui_group": "Emergency Medicine", "journals": ["The Western Journal of Emergency Medicine", "..."]}
  ],
  "journal_to_shards": {
    "The Western Journal of Emergency Medicine": ["shard_00"],
    "JAMA Netw Open": ["shard_03", "shard_04"]
  },
  "ui_groups": [
    {"group": "Emergency Medicine",
     "journals": [{"key": "The Western Journal of Emergency Medicine", "label": "Western J EM", "count": 2066}]}
  ]
}
```
The backend reads this at runtime for: (a) the list of PMC shard corpus IDs to
query, (b) mapping selected journals → shards, (c) serving the journal registry to
the frontend. **Because the app reads the registry dynamically, adding a shard later
needs no app code change — just regenerate the registry and redeploy.**

---

## 3. Ground-truth facts (verified live — trust these over stale files)

**Corpora (all `us-west4`, KNN):**
| Corpus | ID | Files | Action |
|---|---|---|---|
| PMC (live) | `7377459139586293760` | 56,156 | **Keep as rollback** until new shards verified; delete in Phase 6 |
| PMC (abandoned, empty) | `459930111945211904` | ~0 | Delete in Phase 6 |
| local / em-protocols | `2305843009213693952` | 353 | Untouched (stays KNN) |
| wikem | `3379951520341557248` | 1,899 | Untouched |
| litfl | `7991637538768945152` | 7,892 | Untouched |
| rebelem | `1152921504606846976` | 1,245 | Untouched |
| aliem | `4611686018427387904` | 258 | Untouched |
| personal | `2842897264777625600` | — | Untouched |

**Landmine:** `scrapers/PMC/pmc_rag_config.json` points at corpus
`6512768011131158528`, which **no longer exists**. Do NOT trust it. Do NOT run
`scrapers/PMC/pmc_reindex.py`'s `reindex()` — its delete-first logic targets that
dead ID and its region/config assumptions are stale. **Reuse its helper functions,
not its entrypoints.**

**GCS:**
- Bucket `gs://clinical-assistant-457902-pmc` (`us-west4`).
- Processed markdown: `gs://.../processed/` (currently in `batch_00`–`batch_05`).
- Per-article metadata: `gs://.../metadata/{pmcid}.json`, each has a `journal`
  field (and `title`, `year`, `images`, `pmcid`). Read by
  `RAGService._get_pmc_metadata` (`api/rag_service.py:521`).

**Journal distribution (37 journals, 4 UI groups; counts from April 2026 scrape,
mirrored in `frontend/app/page.tsx:30-88`):**

| UI group | Total files | Notes |
|---|---|---|
| Emergency Medicine (12 journals) | 6,962 | fits in 1 shard |
| Critical Care & Resuscitation (7) | 11,436 | → 2 shards (AJRCCM alone is 4,464) |
| JAMA Family (10) | 26,108 | → 4 shards (JAMA Netw Open 9,943 splits across 2) |
| High-Impact General (8) | 11,652 | → 2 shards |
| **Total** | **56,158** | ~9 shards |

(The exact per-journal counts are the source-of-truth `count` fields in
`frontend/app/page.tsx:30-88`; the Phase 1 tool recomputes them live from GCS
metadata rather than trusting these.)

**Concurrency is already cleared as a risk.** A live test fired 5→30 concurrent
`retrieveContexts` calls at the project: **zero throttling errors at every level**
(no 429 / RESOURCE_EXHAUSTED); ~16 concurrent (this design's common case) finished
in ~1.9s wall. So the increase from ~7 to ~16 parallel corpus calls is safe.

**Existing reusable machinery** (`scrapers/PMC/`):
- `pmc_reindex.py`: `_poll_operation()`, `create_corpus()` (KNN default payload),
  `import_gcs_to_corpus()`, `_reorganize_gcs_into_batches()`, parallel GCS ops via
  `ThreadPoolExecutor(max_workers=20)`, auth helpers.
- `import_to_corpus.py`: per-batch import + polling pattern.

**Backend integration points** (`api/rag_service.py`):
- Config block (PMC_CORPUS_ID etc.): lines ~17-34.
- `_retrieve_contexts(query, corpus_name, top_k)`: ~80. Builds the retrieval URL
  from `self.location`; corpus resource region is embedded in `corpus_name`. All
  shards are `us-west4`, so no region change needed.
- `_retrieve_multi_source`: ~907. `ThreadPoolExecutor(max_workers=7)` fan-out with a
  `fetch_pmc()` closure; results merged by score. **This is where shard fan-out
  goes.**
- Journal post-filter (Step 1.5a): ~1080 and ~1174 — filters PMC chunks by
  `pmc_journals`. Keep as the correctness backstop.
- `query_stream`: ~1151.

**Frontend integration points** (`frontend/app/page.tsx`):
- `PMC_JOURNAL_GROUPS`: :30 (hardcoded registry — to be served from backend).
- `selectedJournals` state: :233. `getEffectivePmcJournals()`: :291 (returns
  `undefined` when all selected = no filter, else the selected list).

---

## 4. Phased implementation

### Phase 1 — Shard planner (dry-run, no mutations)
**Goal:** compute the shard layout and write the registry, changing nothing live.

Create `scrapers/PMC/pmc_shard.py`:
1. Build a `pmcid → journal` manifest by reading `gs://.../metadata/*.json` in
   parallel (reuse the `ThreadPoolExecutor` pattern from `pmc_reindex.py`). Cache the
   manifest to disk/GCS so reruns are fast.
2. Compute per-journal live counts; group journals by their UI group.
3. **Group-aligned first-fit-decreasing bin-packing**, cap = `target_cap` (7,500):
   within each UI group, sort journals desc and pack into shards; if a single
   journal exceeds the cap, split its files across consecutive shards in the same
   group. Never mix UI groups in a shard.
4. Write `pmc_shard_registry.json` (Section 2 shape) with `corpus_id: null` for now.
5. `--dry-run` (default) prints the plan; nothing is created/moved.

**Success criteria:**
- [ ] `pmc_shard.py --dry-run` prints a shard plan where **every shard ≤7,500 files**
      and **no shard >10,000**.
- [ ] Sum of all shard file counts **== 56,156** (± known dupes; investigate any gap
      >10).
- [ ] Every one of the 37 journals appears in `journal_to_shards`; each journal maps
      to ≥1 shard; split journals (JAMA Netw Open) map to >1 shard **all within the
      same UI group**.
- [ ] No shard contains journals from more than one UI group.
- [ ] Registry file validates against the Section 2 schema.

### Phase 2 — Create shards + import (the long step)
**Goal:** materialize the shards in Vertex and import the files.
1. Reorganize GCS: move each `.md` into `processed/shard_NN/` per the registry
   (adapt `_reorganize_gcs_into_batches`; parallel). Keep the originals' `batch_*`
   layout untouched OR move from it — either works as long as the live corpus isn't
   re-imported. **Do not touch the live corpus `7377459139586293760`.**
2. Create one KNN corpus per shard in `us-west4` (reuse `create_corpus()`'s payload:
   default `ragManagedDb`, `text-embedding-005`, no `vector_db_config` override).
3. Import each `processed/shard_NN/` folder into its corpus (chunk 1024 / overlap
   200), poll each to completion (reuse `import_gcs_to_corpus` / `_poll_operation`).
4. Write the real `corpus_id`s back into the registry.

**Success criteria:**
- [ ] ~9 new corpora exist in `us-west4`; each shows `corpusStatus.state == ACTIVE`.
- [ ] Each shard's `ragFilesCount` matches its planned count (±dupes) and is ≤7,500.
- [ ] **Sum of all shards' `ragFilesCount` == 56,156** (± known dupes).
- [ ] Registry `corpus_id` fields are all populated (no nulls).
- [ ] The old PMC corpus `7377459139586293760` is untouched (still 56,156 files).

### Phase 3 — Backend: registry-driven multi-shard PMC
**Goal:** query the shards (smart-skipping by journal selection); keep everything
else identical.
1. Load `pmc_shard_registry.json` at `RAGService.__init__` (bundle the file with the
   API image, e.g. copy into `api/` and reference by path; alternative: read from
   GCS at startup). Replace the single `PMC_CORPUS_ID` usage with the shard list.
2. In `_retrieve_multi_source`, when `pmc` is an active source, expand PMC into one
   `_retrieve_contexts` call per **relevant** shard:
   - if `pmc_journals` is None → all shards;
   - else → union of `journal_to_shards[j]` for selected `j`.
   Tag every result `source_type: "pmc"` (existing score-sort, journal post-filter,
   slot allocation, citations then need **no change**).
3. Raise the fan-out pool: `ThreadPoolExecutor(max_workers=...)` from 7 to
   **≥ (non-PMC corpora + max PMC shards)**, ~20.
4. Keep a fallback: an env flag (e.g. `PMC_USE_SHARDS=false` + legacy
   `PMC_CORPUS_ID`) that reverts to querying the single old corpus, for instant
   rollback.
5. Add a lightweight endpoint (e.g. `GET /pmc/journals`) returning the registry's
   `ui_groups` for the frontend.

**Success criteria:**
- [ ] Unit/local run: a query with `sources=["pmc"]` and no journal filter fans out
      to all shards and returns merged, score-ordered PMC contexts.
- [ ] A query with a **subset** of journals selected: logs show **only the shards
      containing those journals were queried** (others skipped), and returned chunks
      are **only** from selected journals (post-filter intact).
- [ ] `GET /pmc/journals` returns the 4 groups / 37 journals with counts.
- [ ] Setting `PMC_USE_SHARDS=false` reverts to the old single-corpus path.
- [ ] `max_workers` ≥ total corpus count; a full all-sources query runs without
      thread starvation (all corpora truly concurrent).

### Phase 4 — Frontend: dynamic journal registry
**Goal:** stop hardcoding journals so future additions need no frontend edit.
1. Fetch `GET /pmc/journals` and render the selection UI from the response, replacing
   the hardcoded `PMC_JOURNAL_GROUPS` (`frontend/app/page.tsx:30`). Keep sending the
   selected journal keys exactly as today (`getEffectivePmcJournals()`).
2. Graceful fallback to the existing hardcoded list if the endpoint fails.

**Success criteria:**
- [ ] Journal selector renders from the backend response; selecting/deselecting
      journals and groups still produces the same `pmc_journals` payload shape.
- [ ] Adding a journal to the backend registry makes it appear in the UI **with no
      frontend code change**.

### Phase 5 — Deploy & verify (the payoff)
1. Deploy backend: `gcloud run deploy em-protocol-api --source . --region us-central1
   --project clinical-assistant-457902` (set `PMC_USE_SHARDS=true`).
2. Run the isolation timing check (method from EMA-97 Experiment 4): measure PMC's
   parallel-shard retrieval contribution.

**Success criteria:**
- [ ] PMC retrieval contribution drops from ~10s to **~1-2s** (max of the parallel
      shard calls).
- [ ] A real `/query` with PMC selected streams an answer with correct PMC citations
      and images; other corpora unaffected.
- [ ] A `/query` with a journal subset returns only those journals and is at least as
      fast.
- [ ] Rollback verified once: `PMC_USE_SHARDS=false` restores prior behavior.

### Phase 6 — Cleanup (only after Phase 5 stable in prod for a few days)
**Success criteria:**
- [ ] Old PMC corpus `7377459139586293760` deleted; abandoned `459930111945211904`
      deleted.
- [ ] `scrapers/PMC/pmc_rag_config.json` removed or updated so it no longer points at
      a dead corpus.
- [ ] `docs/SPEED_AND_SOURCE_STRATEGY.md` / EMA-97 updated noting PMC is now sharded.

---

## 5. Future-growth runbook (the scalability contract)

When PMC is re-scraped or new journals/content are added later:
1. Upload new `.md` + `metadata/*.json` to GCS (existing `pmc_reindex.py` upload
   helpers already do parallel, incremental upload).
2. Re-run `pmc_shard.py`. It recomputes counts and repacks. If any existing shard
   would exceed the **8,500 reshard watermark**, it spills into a new shard and
   updates the registry; otherwise new files append to shards with room.
3. Import only the changed/new shard folders.
4. Redeploy the backend (it re-reads the registry).
The frontend needs no change — it renders from `GET /pmc/journals`. **This same
pattern applies to any future corpus that outgrows 10,000 files** (e.g. if LITFL
grows past the limit): give it a registry + shard fan-out the same way.

## 6. Guardrails / do-not-do
- Do **not** run `pmc_reindex.py reindex()` (deletes the wrong/dead corpus).
- Do **not** delete or re-import the live corpus `7377459139586293760` before Phase
  6.
- Do **not** switch the project to Serverless mode or use `us-central1` for these
  corpora — the whole point is staying on the proven `us-west4` KNN setup.
- Do **not** let any shard exceed 10,000 files; keep ≤7,500 target.
- Keep the journal post-filter (Step 1.5a) even with smart shard-skip — a shard can
  hold both selected and unselected journals.
