# Gemini Search Pilot Rollout

This is the repo-side rollout guide for the two-user Gemini Search pilot.

## Scope

- Pilot users only:
  - `jones.derick@mayo.edu`
  - `morey.jacob@mayo.edu`
- Route behavior:
  - local protocol wording -> local protocol RAG
  - personal-material wording -> personal RAG
  - everything else -> grounded Gemini Search
- Recommended grounded model config:
  - `GEMINI_SEARCH_MODEL=gemini-2.5-flash`
  - `GEMINI_SEARCH_TEMPERATURE=0.5`
  - `GEMINI_SEARCH_MAX_OUTPUT_TOKENS=1200`

## Deploy Backend With Pilot Env Vars

This is the exact deploy command used to preserve the corpus IDs while enabling the Gemini Search pilot:

```bash
gcloud run deploy em-protocol-api \
  --source api/ \
  --project clinical-assistant-457902 \
  --region us-central1 \
  --update-env-vars "^:^PROJECT_NUMBER=930035889332:RAG_LOCATION=us-west4:CORPUS_ID=2305843009213693952:WIKEM_CORPUS_ID=3379951520341557248:PMC_CORPUS_ID=7377459139586293760:LITFL_CORPUS_ID=7991637538768945152:REBELEM_CORPUS_ID=1152921504606846976:ALIEM_CORPUS_ID=4611686018427387904:PERSONAL_CORPUS_ID=2842897264777625600:GEMINI_SEARCH_EXPERIMENT_ENABLED=true:GEMINI_SEARCH_PILOT_EMAILS=jones.derick@mayo.edu,morey.jacob@mayo.edu:GEMINI_SEARCH_MODEL=gemini-2.5-flash:GEMINI_SEARCH_LOCATION=us-central1:GEMINI_SEARCH_TEMPERATURE=0.5:GEMINI_SEARCH_MAX_OUTPUT_TOKENS=1200"
```

Why this form matters:

- Uses `gcloud run deploy` to ship the current backend from `api/`
- Uses `--update-env-vars`, not `--set-env-vars`, so unrelated vars such as `FIREBASE_API_KEY` are preserved
- Explicitly carries all current corpus IDs so the deploy does not rely on code defaults implicitly
- Uses `^:^` as the delimiter so the comma inside `GEMINI_SEARCH_PILOT_EMAILS` is handled safely

## Enable The Pilot On Cloud Run Without Rebuild

If the code is already deployed and you only need to toggle the pilot env vars, run this against the backend service:

```bash
gcloud run services update em-protocol-api \
  --project clinical-assistant-457902 \
  --region us-central1 \
  --update-env-vars=^##^GEMINI_SEARCH_EXPERIMENT_ENABLED=true##GEMINI_SEARCH_PILOT_EMAILS=jones.derick@mayo.edu,morey.jacob@mayo.edu##GEMINI_SEARCH_MODEL=gemini-2.5-flash##GEMINI_SEARCH_LOCATION=us-central1##GEMINI_SEARCH_TEMPERATURE=0.5##GEMINI_SEARCH_MAX_OUTPUT_TOKENS=1200
```

## Smoke Test The Pilot

The repo includes a repeatable end-to-end smoke test:

```bash
python api/smoke_test_gemini_pilot.py
```

What it verifies for each pilot user:

- general clinical prompt -> `route=general_clinical`, `sources=["web"]`
- local prompt -> `route=local_protocol`, `sources=["local"]`
- personal prompt -> `route=personal`, `sources=["personal"]`

The script uses `/auth/corporate-login` to obtain a valid Firebase token, then streams `/query` and checks the `done` event metadata.

## Expected Prompt Checks

Use these prompt styles during live verification:

- General clinical: `How do I manage hyperkalemia with ECG changes?`
- Local protocol: `What is our sepsis protocol?`
- Personal: `Use my personal materials to summarize my uploaded bronchiolitis note.`

## Rollback

Disable the experiment without reverting code:

```bash
gcloud run services update em-protocol-api \
  --project clinical-assistant-457902 \
  --region us-central1 \
  --update-env-vars GEMINI_SEARCH_EXPERIMENT_ENABLED=false
```

## Notes

- Grounded web citations are now normalized to direct destination URLs when possible.
- Grounded web citations are sorted by trust priority:
  - guideline
  - preferred EM journal
  - PubMed / PMC
  - preferred FOAM
  - drug reference
  - general web reference