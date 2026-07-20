# PMC Curated 3-Corpus Workstream

**Status:** In progress — `pmc-em` corpus built and imported, backend/frontend
integration not yet started. **Speed is not confirmed fixed — read §2 before
doing anything else.**
**Tracking:** Linear EMA-97
**Prereq reading:** `docs/SPEED_AND_SOURCE_STRATEGY.md`

This is a self-contained implementation spec — assume no prior context. Follow
phases in order; each has explicit **Success Criteria**. **Read §1 and §2 in
full before touching anything** — this project has already gone through two
prior attempts and a real, still-unresolved finding that changes how you should
approach verification.

---

## 1. Problem & history (read this first)

PMC retrieval takes ~9-10s; every other corpus takes <1-2s. Root cause:
PMC's original corpus has 56,156 files, ~5.6x past Google's documented
10,000-file threshold for the default exact-KNN vector backend
(`ragManagedDb` + `knn`) every corpus in this project uses.

**Attempt 1 (superseded): shard all 56,156 files into 9 correctly-sized KNN
corpora, no content dropped.** Built and imported successfully — every count
verified exact. But isolated speed tests on the fresh shards came back
**slow (7-19s, no better than the original oversized corpus)**, even fully
isolated with zero concurrency, even hours after import (checked at 2h and
4h+, no improvement). Investigation found the whole project runs RAG Engine's
managed Spanner on **Basic tier** — a tiny, fixed 0.1-node (100 processing
unit) instance **shared by every corpus in the region**. The paid fix (Scaled
tier, autoscaling 1-10 nodes) costs **$657-$6,570/month** — rejected as too
expensive. Vector Search 2.0 (the ANN alternative) is *not* meaningfully
cheaper (~$700-800/mo). Pinecone serverless would likely be far cheaper but
needs real integration research — parked, not chosen.

**Attempt 2 (this workstream): don't shard everything — curate down to only
the highest-value journals, in 3 clean, non-split corpora, dropping ~60% of
PMC's content by design.** Content curation is valuable independent of the
speed question (better signal-to-noise for EM-relevant queries; JAMA Netw
Open alone is 9,943 broad-general-medicine articles, ~18% of all of PMC, with
no EM focus). **Built and speed-tested the first corpus (`pmc-em`) as a
decision gate before building the rest — see §2, the result was NOT the clean
pass we hoped for.**

## 2. Honest status of the speed question — READ THIS

A single, freshly-created, correctly-sized (6,959 of 6,960 files, well under
every threshold) corpus (`pmc-em`, corpus ID `1578511669393358848`, `us-west4`,
identical KNN config to every proven-fast corpus) was built and speed-tested
in complete isolation. Result:

```
Run 1: ConnectionError after 13.58s — "Remote end closed connection without response"
Run 2: 11.83s, succeeded
Run 3: 9.96s, succeeded
```

**This rules out "too many simultaneous new corpora" and "corpus too big" as
complete explanations.** A single corpus, correctly sized, behaves identically
to the 9-shard attempt: slow, and in this run, one call didn't even get a
proper response.

The pattern that fits *all* evidence gathered across both attempts: corpora
created **months ago** (LITFL — 7,892 files, comparable size to `pmc-em`'s
6,959 — WikEM, REBEL EM, ALiEM, local) are consistently fast. Corpora created
**today** (the original 9 shards, and now `pmc-em`) are consistently slow —
**regardless of size or count**. The strongest working hypothesis is
**creation recency**, not file count — but this is unconfirmed, and testing
2 and 4+ hours of wait time on `shard_00` showed no improvement. We do not
know the true settling period, or whether one exists at all.

**Decision made anyway: proceed with building all 3 curated corpora.**
Content curation has value independent of whether it fixes speed, and the
infrastructure can be revisited later (e.g. if a much longer wait resolves
it, if Pinecone research pans out, or if the cost calculus on Scaled tier
changes). **Do not assume this workstream fixes the ~10s PMC latency.**
Treat speed verification in Phase 5 as informational, not a hard blocker —
if it's still slow, that is a known, already-anticipated outcome, not a
surprise requiring you to unwind everything. Report it and move on to
deciding next steps with the user, don't silently declare success either way.

**Practical guardrail this finding exposes:** `RAGService._retrieve_contexts`
(`api/rag_service.py`, `_get_access_token` region) issues its
`requests.post(...)` call to Vertex's `retrieveContexts` endpoint with **no
timeout**. During testing this once hung for 18+ minutes on an established
connection with no response. Consider adding an explicit `timeout=` (e.g. 30s)
to this call as part of this workstream's backend work (Phase 3) — currently
a slow/hung PMC shard could block a request indefinitely with no bound.

---

## 3. The curated content set (confirmed with the user)

| Corpus | Journals kept | Files | Status |
|---|---|---|---|
| **pmc-em** | All 12 Emergency Medicine journals: Western J EM, JACEP Open, Am J Emerg Med, Annals of EM, Acad Emerg Med, J Emerg Med, Pediatric Emerg Care, CJEM, Adv J Emerg Med, Prehosp Emerg Care, Eur J Emerg Med, Air Med Journal | 6,960 | **Built.** Corpus ID `1578511669393358848`. Imported 6,959/6,960 (1-file gap — same transient-failure pattern as Attempt 1's 122-file gap, likely fixable with a retry; see Phase 1 remaining task). |
| **pmc-critical-care** | Chest, Crit Care Med, Resuscitation Plus, Shock, Resuscitation, J Intensive Care Med (**dropped: Am J Respir Crit Care Med**, 4,464 files — most pulm-focused, least EM-specific, and the single largest journal in the group) | 6,972 | Not yet built |
| **pmc-high-impact** | Lancet, BMJ, N Engl J Med, Lancet Infect Dis (**dropped: Ann Intern Med, Lancet Respir Med, Mayo Clin Proc, Lancet Neurol** — 2,946 files combined) | 8,706 | Not yet built |
| **Excluded entirely** | **JAMA Family, all 10 journals** (JAMA Netw Open, JAMA, JAMA Intern Med, JAMA Oncol, JAMA Pediatr, JAMA Surg, JAMA Neurol, JAMA Ophthalmol, JAMA Cardiol, JAMA Otolaryngol) — 26,108 files — **plus** Am J Respir Crit Care Med, Ann Intern Med, Lancet Respir Med, Mayo Clin Proc, Lancet Neurol — 7,410 files | **33,518 total excluded** | By design |
| **Total indexed (3 corpora)** | | **22,638** (40% of original PMC's 56,156) | |

Every corpus is well under the 10,000 hard limit and the original 7,500-per-shard
safety target, with **no journal ever split across corpora** — simpler than
Attempt 1's bin-packing, no `journal → [multiple shards]` mapping needed.

This is a real, deliberate content-coverage tradeoff, confirmed with the user —
33,518 articles, more than half of PMC's original content, become unsearchable.
Files are preserved in GCS (moved to a clearly-labeled excluded location, not
deleted), so this is reversible in principle later.

---

## 4. Ground-truth facts (verified live — trust these over stale files)

**Corpora that exist right now (`us-west4`, all KNN/Basic tier):**
| Corpus | ID | Files | Status |
|---|---|---|---|
| Original PMC (live, in production) | `7377459139586293760` | 56,156 | **Keep untouched** — the rollback path until this whole workstream is verified and trusted |
| Abandoned empty PMC dupe | `459930111945211904` | ~0 | Delete during Phase 5 cleanup |
| Attempt 1's 9 shards | `shard_00`–`shard_08`, IDs in the (now-superseded) `pmc_shard_registry.json` — **read that file before overwriting it, to get the exact deletion list** | 56,156 combined | Obsolete once this workstream's 3 corpora are verified; delete during Phase 5 cleanup |
| **pmc-em** (this workstream) | `1578511669393358848` | 6,959/6,960 | **Built** — verify/retry the 1-file gap, otherwise ready to use |
| local / wikem / litfl / rebelem / aliem / personal | unchanged | — | Untouched by any of this |

**Landmine:** `scrapers/PMC/pmc_rag_config.json` points at corpus
`6512768011131158528`, which doesn't exist. Ignore it; remove/fix in Phase 5.
**Do not** run `scrapers/PMC/pmc_reindex.py`'s `reindex()` — delete-first logic
targeting the wrong corpus.

**GCS:**
- Bucket `gs://clinical-assistant-457902-pmc` (`us-west4`).
- Attempt 1 already reorganized all 56,156 files into `processed/shard_00/`
  through `processed/shard_08/` (NOT the original flat `batch_00`-`batch_05`
  layout anymore — that reorg already happened and doesn't need repeating).
  **`processed/shard_00/` IS the Emergency Medicine group** (used as-is for
  `pmc-em`'s import, see below) — the other 8 shard folders contain a
  bin-packed mix of Critical Care/JAMA/High-Impact journals that need to be
  re-split for this workstream's 2 remaining corpora (see Phase 2).
- Per-article metadata: `gs://.../metadata/{pmcid}.json`, each with a `journal`
  field. Read by `RAGService._get_pmc_metadata` (`api/rag_service.py:521`).
  **Critical guardrail, already learned the hard way:** this lookup is
  filename-driven only (`sourceUri`'s last path segment → pmcid →
  `metadata/{pmcid}.json`), NOT folder-path-driven. Any GCS reorg in this
  workstream must preserve filenames exactly and never touch/reorganize the
  `metadata/` prefix, or citation images/titles/journals silently break with
  no error (`_get_pmc_metadata` just returns `None` on a miss).

**Already-built reusable artifacts** (`scrapers/PMC/`), don't rebuild these:
- `pmc_journal_manifest.json` — full `{pmcid: journal}` map for all 56,156
  files, already cached. Reuse directly; no need to re-read GCS metadata.
- `pmc_shard_assignments.json` — Attempt 1's `{shard_id: [pmcids]}`. `shard_00`
  is exactly the Emergency Medicine group's pmcid list (already used to build
  `pmc-em`). The other shards' pmcid lists are a mixed bag from Attempt 1's
  bin-packer and are **not** directly reusable for this workstream's group
  boundaries — recompute the Critical Care and High-Impact pmcid lists fresh
  from `pmc_journal_manifest.json` instead (filter by the confirmed journal
  lists in §3).
- `pmc_shard_registry.json` — Attempt 1's registry (9-shard schema). Superseded
  by this workstream's simpler schema (§Phase 2 step 4) — read it once for the
  shard corpus IDs (needed for Phase 5 cleanup), then it can be replaced.
- `pmc_create_one.py` — the script used to build `pmc-em`. Reuse its
  create-corpus and import-with-polling pattern for the other 2 corpora
  (generalize it to take a display name + GCS source URI, rather than writing
  new one-off scripts per corpus).
- `pmc_shard_migrate.py` — Attempt 1's GCS-move + create + import script.
  Useful reference for the parallel move pattern (`ThreadPoolExecutor`,
  copy_blob + delete, resumable-by-checking-destination-exists) — reuse the
  *pattern*, not the shard-specific logic.

**Backend integration points** (`api/rag_service.py`, from Attempt 1's partial
build — still present in the working tree, needs updating not rewriting):
- Config block (~line 17-34): `PMC_USE_SHARDS`, `PMC_SHARD_REGISTRY_PATH`.
- `__init__` (~line 48-90): loads the registry, builds `self.pmc_shards`,
  `self.pmc_journal_to_shards`, `self.pmc_ui_groups`, computes
  `self._retrieval_pool_size`.
- `_load_pmc_shard_registry()`: parses the registry JSON — **needs updating**
  for this workstream's simpler schema (§Phase 2 step 4: `journal_to_corpus`
  is a single string per journal, not a list).
- `_relevant_pmc_shards(pmc_journals)`: shard-selection logic — **simplifies**
  under the new schema (straight lookup + dedupe, no union-of-lists).
- `fetch_pmc_shard(shard)` + the `ThreadPoolExecutor` fan-out in
  `_retrieve_multi_source` (~line 1096): **unchanged in shape**, just fans out
  over 3 corpora instead of 9.
- `_get_images_from_contexts`, journal post-filter (Step 1.5a, ~line 1080 &
  1174): **unchanged** — both are already source/shard-agnostic.
- `GET /pmc/journals` endpoint already added to `api/main.py` — update the
  response to reflect only the 3 corpora's journals once the registry changes.

**Frontend integration points** (`frontend/app/page.tsx`):
- `PMC_JOURNAL_GROUPS` (line ~30): hardcoded, includes all 37 journals —
  **must be updated or replaced** (Phase 4) since 15 of those journals will no
  longer be indexed anywhere; leaving it as-is would offer filter options for
  content that doesn't exist.
- `selectedJournals` state (~233), `getEffectivePmcJournals()` (~291): no
  contract change needed.

---

## 5. Phased implementation

### Phase 1 — Finish `pmc-em` (mostly done)

1. Investigate the 1-file import gap (6,959 of 6,960). Use the same method as
   Attempt 1's 122-file investigation: list actual indexed files via the
   `ragFiles` list endpoint (paginate with a delay between pages — Attempt 1
   hit a 429 quota error pacing too fast), diff against
   `pmc_shard_assignments.json["shard_00"]`, retry the missing file's specific
   GCS URI via a small `ragFiles:import` call.
2. Re-verify count == 6,960.

**Success criteria:**
- [ ] `pmc-em` corpus `ragFilesCount == 6960`.

### Phase 2 — Build `pmc-critical-care` and `pmc-high-impact`

1. From `pmc_journal_manifest.json`, compute the pmcid lists for each corpus
   using the confirmed journal sets in §3 (simple filter, no bin-packing).
2. Reorganize GCS: move each corpus's `.md` files into
   `processed/pmc-critical-care/` and `processed/pmc-high-impact/`
   respectively (files currently live somewhere under Attempt 1's
   `processed/shard_01/` through `shard_08/` — build a
   `pmcid → current location` map by listing those prefixes, same pattern as
   Attempt 1's `pmc_shard_migrate.py:build_current_location_map`). Move the
   33,518 excluded-journal files to `processed/pmc-excluded/` (preserve, don't
   delete). **Preserve filenames exactly; never touch `metadata/`** (§4).
3. Create both corpora (reuse/generalize `pmc_create_one.py`'s pattern — same
   KNN config, `text-embedding-005`, chunk 1024/overlap 200).
4. Import each, verify counts (6,972 / 8,706).
5. Write `scrapers/PMC/pmc_shard_registry.json` (**overwrite** — Attempt 1's
   version is superseded; you already extracted the old shard IDs for cleanup
   in §4). Simplified schema:
   ```json
   {
     "location": "us-west4",
     "corpora": [
       {"id": "pmc_em", "corpus_id": "1578511669393358848", "file_count": 6960, "journals": ["The Western Journal of Emergency Medicine", "..."]},
       {"id": "pmc_critical_care", "corpus_id": "<new id>", "file_count": 6972, "journals": ["Chest", "..."]},
       {"id": "pmc_high_impact", "corpus_id": "<new id>", "file_count": 8706, "journals": ["Lancet", "..."]}
     ],
     "journal_to_corpus": {"The Western Journal of Emergency Medicine": "pmc_em", "Chest": "pmc_critical_care", "...": "..."},
     "excluded_journals": ["JAMA Netw Open", "JAMA", "...", "Am J Respir Crit Care Med", "Ann Intern Med", "Lancet Respir Med", "Mayo Clin Proc", "Lancet Neurol"],
     "ui_groups": [
       {"group": "Emergency Medicine", "journals": [{"key": "...", "count": 2064}, "..."]},
       {"group": "Critical Care & Resuscitation", "journals": [...]},
       {"group": "High-Impact General", "journals": [...]}
     ]
   }
   ```
   Note: **every journal maps to exactly one corpus (a string)**, not a list —
   this is the key simplification vs. Attempt 1's schema.

**Success criteria:**
- [ ] `pmc-critical-care` and `pmc-high-impact` corpora created, `ragFilesCount`
      6,972 and 8,706 respectively.
- [ ] Sum of all 3 corpora + excluded count == 56,156 (no files unaccounted for).
- [ ] Spot-check `_get_pmc_metadata()` resolves correctly for ~10 pmcids sampled
      across all 3 corpora (the metadata/filename guardrail from §4).
- [ ] New registry validates: every journal in §3's kept lists appears in
      `journal_to_corpus`; every excluded journal appears in `excluded_journals`;
      no journal appears in both.

### Phase 3 — Backend integration

Update (not rewrite) the existing scaffolding in `api/rag_service.py` (§4):
1. `_load_pmc_shard_registry()`: parse the new schema — `corpora` list,
   `journal_to_corpus` single-value map.
2. `_relevant_pmc_shards(pmc_journals)`: simplify to — no filter → all 3
   corpora; else → `{journal_to_corpus[j] for j in pmc_journals if j in
   journal_to_corpus}` (excluded journals silently contribute nothing, which
   is correct — they were never indexed).
3. **Add an explicit timeout** to the `retrieveContexts` call in
   `_retrieve_contexts` (currently has none — see §2's practical guardrail;
   the 18-minute hang observed during testing should not be possible in
   production code). Something like `timeout=30` on the `requests.post` call,
   with a clear exception path (log + return empty results for that source,
   same pattern as the existing per-corpus `try/except` in
   `_retrieve_multi_source`'s fetch closures) rather than letting a single
   slow/hung PMC corpus block the whole request.
4. `_retrieval_pool_size`: recompute (6 non-PMC + up to 3 PMC + headroom —
   can shrink back from Attempt 1's ~20 since concurrency is no longer a
   concern at 3 corpora).
5. `GET /pmc/journals` (`api/main.py`): confirm it now returns only the 3
   corpora's journals via the updated registry.

**Success criteria:**
- [ ] A query with `sources=["pmc"]`, no journal filter, fans out to exactly
      3 corpora and returns merged, score-ordered results.
- [ ] A query with a journal subset selected only queries the corpus/corpora
      containing those journals (check `[rag-timing]` logs for which `pmc:*`
      keys appear).
- [ ] Selecting an excluded journal (e.g. `"JAMA"`) returns zero PMC results
      without error (correctly a no-op, not a crash).
- [ ] The new timeout is verified to actually trigger: simulate or test
      against a slow/unresponsive endpoint and confirm the request fails
      gracefully within the timeout window rather than hanging.
- [ ] `GET /pmc/journals` returns exactly 3 groups matching §3's kept lists.

### Phase 4 — Frontend

1. Fetch `GET /pmc/journals` and render the selector dynamically, replacing
   the hardcoded `PMC_JOURNAL_GROUPS` (`frontend/app/page.tsx:30`). Graceful
   fallback if the endpoint fails.
2. Keep `getEffectivePmcJournals()`'s contract unchanged (still sends selected
   keys, `undefined` when everything's selected).

**Success criteria:**
- [ ] Journal selector shows only the 3 corpora's journals (EM's 12, Critical
      Care's 6, High-Impact's 4) — 22 total, not 37.
- [ ] Selecting/deselecting still produces the same `pmc_journals` payload shape
      as before.

### Phase 5 — Deploy, verify, clean up

1. Deploy: `gcloud run deploy em-protocol-api --source . --region us-central1
   --project clinical-assistant-457902`.
2. **Speed check — informational, not a blocking gate** (§2): run the same
   isolated + full-fan-out timing tests used throughout this investigation.
   Report honestly whether it's fast or still slow. If still slow, that
   confirms §2's finding rather than being a new failure — do not treat it as
   something to silently fix or hide; report it and let the user decide next
   steps (accept as-is with the content-curation benefit alone, wait longer,
   revisit Pinecone, or reconsider Scaled tier).
3. Correctness verification (regardless of speed outcome): a real `/query`
   with PMC selected returns correct citations/images from the 3 curated
   corpora; journal-filtered queries behave correctly; other corpora
   unaffected.
4. **Cleanup**, only after this workstream is confirmed stable in production
   for a few days:
   - Delete Attempt 1's 9 obsolete shard corpora (IDs from the old registry,
     extracted in §4).
   - Delete the abandoned empty PMC dupe corpus (`459930111945211904`).
   - Keep the original live PMC corpus (`7377459139586293760`) as rollback
     until full confidence in the new setup; delete only after that.
   - Fix/remove the stale `scrapers/PMC/pmc_rag_config.json`.

**Success criteria:**
- [ ] Deployed and serving.
- [ ] Correctness criteria in step 3 all pass.
- [ ] Speed outcome is measured and reported honestly, whatever it is.
- [ ] Cleanup only performed after explicit confirmation the new setup is
      trusted — not automatic.

---

## 6. Future-growth runbook

If PMC content is revisited later (adding journals back, or adding wholly new
ones): update `pmc_journal_manifest.json` (or re-derive from GCS metadata),
decide which corpus a new/returning journal belongs to (or whether it needs a
new 4th corpus, keeping each under the 7,500-9,000 range that's worked so
far), update `journal_to_corpus` and `ui_groups` in the registry, move its
files into the right GCS folder, import, redeploy. The registry-driven design
means the backend needs no code changes for this — only Phase 4's frontend
fetch already handles new groups/journals dynamically.

**If the speed question ever gets resolved** (much longer wait proves
sufficient, Pinecone research pans out, or Scaled tier becomes acceptable),
the previously-excluded 33,518 articles in `processed/pmc-excluded/` are
still there, ready to be re-indexed without re-scraping.

## 7. Guardrails / do-not-do

- Do **not** run `pmc_reindex.py reindex()` (deletes the wrong/dead corpus).
- Do **not** touch the live corpus `7377459139586293760` until Phase 5
  cleanup, and only after explicit confirmation.
- Do **not** switch the project to Serverless mode or use `us-central1` —
  same reasoning as Attempt 1, still applies.
- Do **not** rename files during any GCS move, and never reorganize
  `metadata/*.json` — breaks citation images/titles/journals silently (§4).
- Do **not** treat a fast Phase 5 speed check as proof the underlying Basic-
  tier issue is solved, and do **not** treat a slow one as a reason to revert
  everything — §2 already established this is a known, open question
  independent of this workstream's content-curation goal.
- Do **not** skip adding the `retrieveContexts` timeout (Phase 3, step 3) —
  a real 18-minute hang was observed during this investigation with no
  timeout in place.
