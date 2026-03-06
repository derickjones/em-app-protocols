# Personal RAG — MVP Implementation Plan

## Overview

Allow users to upload their own files (PDFs, images, text) into a personal knowledge base that integrates with the existing multi-source RAG search. Each user's content is isolated — only they can see and search their files.

**MVP Scope:** Upload, process, index, search, delete. No fancy UI — just functional.

---

## Architecture

```
                    ┌─────────────┐
                    │   Frontend   │
                    │  "My Files"  │
                    │  sidebar +   │
                    │  upload page │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   API        │
                    │  /personal/* │
                    │  endpoints   │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │   GCS    │ │ Firestore│ │ Vertex AI│
        │  Bucket  │ │ File     │ │ RAG      │
        │ per-user │ │ Registry │ │ Corpus   │
        │ prefix   │ │          │ │ (shared) │
        └──────────┘ └──────────┘ └──────────┘
```

### Key Decision: Dedicated RAG Corpus for Personal Files

Create ONE new Vertex AI RAG corpus for all personal uploads. Files are tagged with `user_id` via the GCS path prefix (`gs://bucket/{uid}/filename.txt`). At query time, filter retrieval results by the requesting user's file paths.

This keeps personal content completely separate from the curated ED Universe and Mayo protocol corpora.

---

## 1. GCS Bucket

**Bucket:** `clinical-assistant-457902-personal`

**Structure:**
```
gs://clinical-assistant-457902-personal/
  {uid}/
    {file_id}.txt          ← extracted text (indexed by RAG)
    {file_id}.original     ← original uploaded file (for preview/download)
    {file_id}.meta.json    ← extraction metadata
```

**Per-user quota:** 50 files, 200MB total

---

## 2. Firestore Schema

```
users/{uid}/personal_files/{file_id}
  - filename: "cardiac_notes.pdf"          // original filename
  - file_id: "pf_1709654321_abc123"        // unique ID
  - gcs_original: "gs://.../{uid}/{file_id}.original"
  - gcs_text: "gs://.../{uid}/{file_id}.txt"
  - status: "processing" | "indexed" | "failed"
  - error: null | "Failed to extract text"
  - content_type: "application/pdf"
  - size_bytes: 245000
  - chunk_count: 12                        // set after indexing
  - uploaded_at: timestamp
  - indexed_at: timestamp | null
```

---

## 3. API Endpoints

All endpoints require Firebase auth token.

### `POST /personal/upload`
- Accepts multipart file upload
- Validates: file type (PDF, PNG, JPG, TXT, MD), size (<20MB), user quota
- Saves original to GCS `{uid}/{file_id}.original`
- Extracts text:
  - PDF → PyMuPDF text extraction; if empty pages → Gemini Vision fallback
  - Images → Gemini Vision description
  - TXT/MD → direct use
- Saves extracted text to GCS `{uid}/{file_id}.txt`
- Indexes text file into personal RAG corpus
- Creates Firestore doc with status tracking
- Returns: `{ file_id, filename, status }`

### `GET /personal/files`
- Returns list of user's files from Firestore
- Sorted by `uploaded_at` desc
- Includes status, filename, size, chunk_count

### `DELETE /personal/files/{file_id}`
- Deletes GCS files (original + text + meta)
- Deletes from RAG corpus (by GCS URI)
- Deletes Firestore doc
- Returns: `{ success: true }`

### `GET /personal/files/{file_id}/status`
- Returns current processing status (for polling after upload)

### `GET /personal/quota`
- Returns: `{ files_used: 12, files_limit: 50, bytes_used: 15000000, bytes_limit: 209715200 }`

---

## 4. Processing Pipeline

Runs inline in the API (not a separate Cloud Function for MVP). For large files, could move to background task.

```python
async def process_personal_file(uid: str, file_id: str, content_type: str):
    """Extract text from uploaded file and index into RAG corpus"""
    
    # 1. Download original from GCS
    # 2. Extract text based on content_type
    #    - PDF: PyMuPDF → pages of text; fallback to Gemini Vision for empty pages
    #    - Image: Gemini Vision → description
    #    - Text: direct read
    # 3. Upload extracted text to GCS as {file_id}.txt
    # 4. Index into personal RAG corpus via importRagFiles API
    # 5. Update Firestore status → "indexed"
```

---

## 5. RAG Integration

### New corpus
```
PERSONAL_CORPUS_ID = env var (created via Vertex AI console or API)
PERSONAL_BUCKET = "clinical-assistant-457902-personal"
```

### Query modification in `rag_service.py`

When `sources` includes `"personal"`:
1. Retrieve contexts from personal corpus (top_k=5)
2. Filter results: only include contexts where `source_uri` starts with `gs://.../{requesting_user_uid}/`
3. Merge with other source results by relevance score

```python
def _retrieve_personal_contexts(self, query: str, user_id: str, top_k: int = 5):
    """Retrieve from personal corpus, filtered to this user's files only"""
    contexts = self._retrieve_contexts(query, self.personal_corpus_name, top_k=top_k * 3)
    # Filter to only this user's files
    user_prefix = f"gs://{PERSONAL_BUCKET}/{user_id}/"
    return [c for c in contexts if c["source"].startswith(user_prefix)][:top_k]
```

### Citation display
Personal results get source_type `"personal"` and display the original filename.

---

## 6. Frontend

### Sidebar Addition (in Settings section of `page.tsx`)

Between "ED Universe" and "Mayo Clinic Protocols":

```
┌─────────────────────────────┐
│ 📁 My Files                 │
│   ☑ Include in search       │
│   12 files · 14.2 MB        │
│   [Manage Files]            │
└─────────────────────────────┘
```

- Toggle checkbox to include/exclude `"personal"` from `getEffectiveSources()`
- "Manage Files" links to `/personal` page

### Upload Page (`/personal/page.tsx`)

Simple page:
- File picker button (accept: .pdf, .png, .jpg, .txt, .md)
- ⚠️ PHI warning banner at top
- File list table: filename, status badge, size, date, delete button
- Quota bar: "12 / 50 files · 14.2 MB / 200 MB"

### PHI Warning

Displayed prominently on the upload page:

```
⚠️ Do not upload files containing Protected Health Information (PHI),
   patient names, medical record numbers, or other identifiable patient data.
```

Also shown as a one-time confirmation dialog on first upload.

---

## 7. RAG Corpus Creation

Run once to create the personal corpus:

```bash
curl -X POST \
  "https://us-west4-aiplatform.googleapis.com/v1beta1/projects/930035889332/locations/us-west4/ragCorpora" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "display_name": "personal-user-files",
    "description": "Personal user-uploaded files for individual RAG search",
    "rag_embedding_model_config": {
      "vertex_prediction_endpoint": {
        "endpoint": "projects/930035889332/locations/us-central1/publishers/google/models/text-embedding-004"
      }
    }
  }'
```

---

## 8. Implementation Order

| Step | What | Est. |
|------|------|------|
| 1 | Create GCS bucket + RAG corpus | 15 min |
| 2 | API: upload endpoint + text extraction | 3 hrs |
| 3 | API: file list, delete, quota endpoints | 1 hr |
| 4 | RAG: personal source integration in rag_service.py | 1 hr |
| 5 | Frontend: /personal upload page | 2 hrs |
| 6 | Frontend: sidebar "My Files" toggle | 30 min |
| 7 | Frontend: citation attribution for personal results | 30 min |
| 8 | Testing + deploy | 1 hr |
| **Total** | | **~1.5 days** |

---

## 9. Environment Variables (New)

```
PERSONAL_CORPUS_ID=2842897264777625600
PERSONAL_BUCKET=clinical-assistant-457902-personal
PERSONAL_FILE_LIMIT=50
PERSONAL_BYTES_LIMIT=209715200
```

---

## 10. Future Enhancements (Post-MVP)

- Drag & drop upload
- Extracted text preview ("see what the AI indexed")
- In-file search (search within your files, not RAG)
- Folder organization
- Share files with team members
- OCR for scanned PDFs (Gemini Vision per-page)
- DOCX / PPTX support
