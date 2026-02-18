# LITFL Indexer Quick Reference

## Prerequisites

```bash
# Ensure you have the required packages (should already be installed)
pip install google-cloud-storage google-auth requests
```

## Step-by-Step Usage

### Step 1: Create the RAG Corpus (One-time, ~30 seconds)

```bash
cd scrapers/litfl
python litfl_indexer.py --create-corpus
```

This will:
- Create a new Vertex AI RAG corpus named "litfl-foamed"
- Save the configuration to `litfl_rag_config.json`
- Output the corpus ID and details

### Step 2: Index All Files (~2-4 hours with 10 workers)

```bash
python litfl_indexer.py --index-all --workers 10
```

This will:
- Index all 7,902 markdown files from `output/processed/`
- Upload metadata for each file (images, attribution, etc.)
- Use 10 parallel workers to speed up the process
- Show progress every 100 files
- Display ETA and completion stats

**Progress tracking:**
- Every 100 files, you'll see: `Progress: 500/7902 (498 success, 2 failed) - ETA: 45.3min`
- Final summary shows total time and success/failure counts

### Step 3: Verify Indexing

```bash
# Check corpus status
python litfl_indexer.py --status

# List first 20 indexed files
python litfl_indexer.py --list-files

# Validate all files are indexed
python litfl_indexer.py --validate
```

## Additional Commands

### Index a Single File (for testing)

```bash
python litfl_indexer.py --index-file output/processed/etomidate.md
```

### Check Configuration

```bash
cat litfl_rag_config.json
```

Example output:
```json
{
  "project_id": "clinical-assistant-457902",
  "project_number": "930035889332",
  "location": "us-west4",
  "corpus_id": "1234567890123456789",
  "corpus_name": "projects/930035889332/locations/us-west4/ragCorpora/1234567890123456789",
  "corpus_display_name": "litfl-foamed",
  "embedding_model": "text-embedding-005",
  "created_at": "2026-02-17T20:30:00Z",
  "last_indexed": "2026-02-17T23:45:00Z",
  "total_files_indexed": 7902,
  "indexing_failures": 0
}
```

## Troubleshooting

### Authentication Issues

```bash
# Ensure you're authenticated with Google Cloud
gcloud auth application-default login

# Set your project
gcloud config set project clinical-assistant-457902
```

### Check GCS Bucket

```bash
# List files in the bucket
gsutil ls gs://clinical-assistant-457902-litfl/processed/ | head -20

# Check metadata files
gsutil ls gs://clinical-assistant-457902-litfl/metadata/ | head -20
```

### Resume Interrupted Indexing

The indexer is idempotent - you can safely re-run `--index-all` if it gets interrupted. Files already indexed won't be re-indexed unless they've changed.

### Validation Failures

If `--validate` shows missing files:

```bash
# Re-index missing files
python litfl_indexer.py --index-all --workers 5
```

## Performance Tuning

### Worker Count

- **--workers 5** (default): Safe, moderate speed
- **--workers 10**: Faster, recommended for initial indexing
- **--workers 20**: Very fast, but may hit rate limits

### Expected Times

| Workers | Estimated Time |
|---------|---------------|
| 5       | ~4-5 hours    |
| 10      | ~2-3 hours    |
| 20      | ~1-2 hours    |

## Next Steps After Indexing

1. **Update environment variables** in your backend:
   ```bash
   # Add to .env or deployment config
   LITFL_CORPUS_ID="<corpus_id_from_config>"
   ```

2. **Update `api/rag_service.py`** to query LITFL corpus

3. **Test queries** that should pull LITFL content:
   - "What's the pharmacokinetics of etomidate?"
   - "Show me ECG examples of Wellens syndrome"
   - "What's the management of beta blocker overdose?"

4. **Update frontend** to display LITFL citations with proper attribution

## Monitoring

### During Indexing

Watch the logs for:
- ✅ Success indicators
- ⚠️ Warning messages (non-fatal)
- ❌ Error messages (investigate these)

### After Indexing

```bash
# Get detailed status
python litfl_indexer.py --status

# Count indexed files
python litfl_indexer.py --list-files | wc -l

# Should output: 7902 (or close to it)
```

## Files Created

```
scrapers/litfl/
├── litfl_indexer.py              # ← New indexer script
├── litfl_rag_config.json         # ← Auto-generated after --create-corpus
└── output/
    ├── processed/                # Existing: 7,716 .md files (input)
    └── metadata/                 # Existing: metadata files
```

## Cost Tracking

- **Corpus creation**: Free
- **Embedding**: ~$0.50 for 7,902 files
- **Storage**: ~$1/month
- **Queries**: ~$0.002 each

**Total one-time cost**: ~$0.50  
**Monthly ongoing**: ~$1-2
