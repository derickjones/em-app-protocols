"""
Personal RAG Service
Handles user file uploads, text extraction, and indexing into the personal RAG corpus.
"""

import os
import io
import json
import hashlib
import time
import requests
import google.auth
import google.auth.transport.requests
from google.cloud import storage, firestore
from typing import Dict, Optional, Tuple

# Configuration
PROJECT_ID = os.environ.get("PROJECT_ID", "clinical-assistant-457902")
PROJECT_NUMBER = os.environ.get("PROJECT_NUMBER", "930035889332")
RAG_LOCATION = os.environ.get("RAG_LOCATION", "us-west4")
PERSONAL_CORPUS_ID = os.environ.get("PERSONAL_CORPUS_ID", "2842897264777625600")
PERSONAL_BUCKET = os.environ.get("PERSONAL_BUCKET", "clinical-assistant-457902-personal")
PERSONAL_FILE_LIMIT = int(os.environ.get("PERSONAL_FILE_LIMIT", "50"))
PERSONAL_BYTES_LIMIT = int(os.environ.get("PERSONAL_BYTES_LIMIT", str(200 * 1024 * 1024)))  # 200MB
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20MB per file
MAX_PDF_PAGES = 500

ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "text/plain": ".txt",
    "text/markdown": ".md",
}

# HEIC/HEIF types that need conversion to JPEG for browser/Gemini compatibility
HEIC_TYPES = {"image/heic", "image/heif"}


class PersonalService:
    """Service for managing personal user file uploads and RAG indexing"""

    def __init__(self):
        self.storage_client = storage.Client()
        self.db = firestore.Client()
        self.bucket = self.storage_client.bucket(PERSONAL_BUCKET)
        self.corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{PERSONAL_CORPUS_ID}"

    def _get_access_token(self) -> str:
        """Get OAuth2 access token"""
        credentials, _ = google.auth.default()
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        return credentials.token

    # ─── Quota ────────────────────────────────────────────────────────────

    def get_quota(self, uid: str) -> Dict:
        """Get current usage and limits for a user"""
        files_ref = self.db.collection("users").document(uid).collection("personal_files")
        docs = files_ref.stream()

        files_used = 0
        bytes_used = 0
        for doc in docs:
            data = doc.to_dict()
            if data.get("status") != "failed":
                files_used += 1
                bytes_used += data.get("size_bytes", 0)

        return {
            "files_used": files_used,
            "files_limit": PERSONAL_FILE_LIMIT,
            "file_count": files_used,
            "file_limit": PERSONAL_FILE_LIMIT,
            "bytes_used": bytes_used,
            "bytes_limit": PERSONAL_BYTES_LIMIT,
        }

    def _check_quota(self, uid: str, new_file_bytes: int) -> Optional[str]:
        """Check if user has quota for a new file. Returns error message or None."""
        quota = self.get_quota(uid)
        if quota["files_used"] >= quota["files_limit"]:
            return f"File limit reached ({quota['files_limit']} files). Delete some files to upload more."
        if quota["bytes_used"] + new_file_bytes > quota["bytes_limit"]:
            used_mb = quota["bytes_used"] / (1024 * 1024)
            limit_mb = quota["bytes_limit"] / (1024 * 1024)
            return f"Storage limit reached ({used_mb:.1f}MB / {limit_mb:.0f}MB). Delete some files to free space."
        return None

    # ─── HEIC/HEIF Conversion ────────────────────────────────────────────

    def _convert_heic_to_jpeg(self, file_bytes: bytes, filename: str) -> Tuple[bytes, str, str]:
        """Convert HEIC/HEIF image to JPEG. Returns (jpeg_bytes, 'image/jpeg', new_filename)."""
        from PIL import Image
        import pillow_heif

        # Register HEIF opener with Pillow
        pillow_heif.register_heif_opener()

        img = Image.open(io.BytesIO(file_bytes))

        # Handle EXIF rotation
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)

        # Convert to RGB (HEIC can be RGBA or other modes)
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Save as JPEG
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        jpeg_bytes = buf.getvalue()

        # Update filename extension
        base = filename.rsplit(".", 1)[0] if "." in filename else filename
        new_filename = f"{base}.jpg"

        print(f"Converted HEIC ({len(file_bytes)} bytes) → JPEG ({len(jpeg_bytes)} bytes)")
        return jpeg_bytes, "image/jpeg", new_filename

    # ─── Text Extraction ──────────────────────────────────────────────────

    def _extract_text_from_pdf(self, file_bytes: bytes) -> str:
        """Extract text from a PDF using PyMuPDF. Falls back to Gemini Vision for empty pages."""
        import fitz  # PyMuPDF

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as e:
            raise ValueError(f"Could not open PDF: the file may be corrupted, encrypted, or not a valid PDF. ({e})")

        try:
            if doc.page_count > MAX_PDF_PAGES:
                raise ValueError(f"PDF has {doc.page_count} pages (max {MAX_PDF_PAGES}). Please upload a shorter document.")

            pages_text = []
            empty_pages = []

            for i, page in enumerate(doc):
                try:
                    text = page.get_text().strip()
                except Exception as e:
                    print(f"Warning: failed to extract text from page {i + 1}: {e}")
                    text = ""
                if text:
                    pages_text.append(f"--- Page {i + 1} ---\n{text}")
                else:
                    empty_pages.append(i)
        finally:
            doc.close()

        # Fallback: use Gemini Vision for pages with no extractable text (scanned PDFs)
        if empty_pages and len(empty_pages) <= 10:
            for page_num in empty_pages:
                try:
                    vision_text = self._extract_with_gemini_vision(file_bytes, page_num=page_num)
                    if vision_text:
                        pages_text.append(f"--- Page {page_num + 1} (OCR) ---\n{vision_text}")
                except Exception as e:
                    print(f"Gemini Vision fallback failed for page {page_num + 1}: {e}")

        return "\n\n".join(pages_text)

    def _extract_text_from_image(self, file_bytes: bytes, content_type: str) -> str:
        """Extract description from an image using Gemini Vision"""
        return self._extract_with_gemini_vision(file_bytes, content_type=content_type)

    def _extract_with_gemini_vision(self, file_bytes: bytes, page_num: int = None, content_type: str = "image/png") -> str:
        """Use Gemini to describe an image or a PDF page"""
        import base64

        # If extracting a specific PDF page, render it to an image first
        if page_num is not None:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            try:
                page = doc[page_num]
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
            finally:
                doc.close()
            mime = "image/png"
        else:
            img_bytes = file_bytes
            mime = content_type

        b64 = base64.b64encode(img_bytes).decode("utf-8")

        url = f"https://us-west4-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/us-west4/publishers/google/models/gemini-2.0-flash:generateContent"
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
        }
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Describe this medical/clinical image or document page in detail. Extract all visible text, labels, data, and clinical information. Be thorough and structured."},
                    {"inline_data": {"mime_type": mime, "data": b64}},
                ]
            }],
            "generation_config": {"max_output_tokens": 2048, "temperature": 0.1},
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            raise Exception(f"Gemini Vision failed: {resp.status_code}")

        result = resp.json()
        candidates = result.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            return parts[0].get("text", "") if parts else ""
        return ""

    # ─── Upload + Process ─────────────────────────────────────────────────

    def upload_and_process(self, uid: str, filename: str, content_type: str, file_bytes: bytes) -> Dict:
        """
        Upload a file, extract text, index into RAG corpus, and track in Firestore.
        Returns file metadata dict.
        """
        # Validate content type
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError(f"Unsupported file type: {content_type}. Allowed: PDF, PNG, JPG, HEIC, TXT, MD")

        # Validate size
        if len(file_bytes) > MAX_UPLOAD_SIZE:
            max_mb = MAX_UPLOAD_SIZE / (1024 * 1024)
            raise ValueError(f"File too large ({len(file_bytes) / (1024*1024):.1f}MB). Max: {max_mb:.0f}MB per file.")

        # Convert HEIC/HEIF → JPEG (browsers & Gemini don't support HEIC)
        if content_type in HEIC_TYPES:
            file_bytes, content_type, filename = self._convert_heic_to_jpeg(file_bytes, filename)

        # Check quota
        quota_err = self._check_quota(uid, len(file_bytes))
        if quota_err:
            raise ValueError(quota_err)

        # Generate file ID
        file_hash = hashlib.sha256(file_bytes).hexdigest()[:8]
        file_id = f"pf_{int(time.time())}_{file_hash}"

        # Check for duplicate (same hash)
        existing = self.db.collection("users").document(uid).collection("personal_files") \
            .where("sha256_prefix", "==", file_hash).limit(1).stream()
        for doc in existing:
            existing_data = doc.to_dict()
            raise ValueError(f"This file was already uploaded as '{existing_data.get('filename', 'unknown')}'")

        # Create Firestore doc with "processing" status
        file_doc = {
            "filename": filename,
            "file_id": file_id,
            "status": "processing",
            "error": None,
            "content_type": content_type,
            "size_bytes": len(file_bytes),
            "sha256_prefix": file_hash,
            "chunk_count": 0,
            "uploaded_at": firestore.SERVER_TIMESTAMP,
            "indexed_at": None,
        }
        self.db.collection("users").document(uid).collection("personal_files").document(file_id).set(file_doc)

        try:
            # 1. Save original to GCS
            original_blob = self.bucket.blob(f"{uid}/{file_id}.original")
            original_blob.upload_from_string(file_bytes, content_type=content_type)

            # 2. Extract text (no page rendering — images rendered on-demand at query time)
            if content_type == "application/pdf":
                extracted_text = self._extract_text_from_pdf(file_bytes)
            elif content_type.startswith("image/"):
                extracted_text = self._extract_text_from_image(file_bytes, content_type)
            else:
                # Plain text or markdown
                extracted_text = file_bytes.decode("utf-8", errors="replace")

            if not extracted_text.strip():
                raise ValueError("No text could be extracted from this file.")

            # Prepend filename as context for the RAG
            extracted_text = f"Source file: {filename}\n\n{extracted_text}"

            # 3. Save extracted text to GCS
            text_blob = self.bucket.blob(f"{uid}/{file_id}.txt")
            text_blob.upload_from_string(extracted_text.encode("utf-8"), content_type="text/plain")
            text_uri = f"gs://{PERSONAL_BUCKET}/{uid}/{file_id}.txt"

            # 4. Index into personal RAG corpus
            chunk_count = self._index_to_corpus(text_uri)

            # 5. Update Firestore with success
            # Note: no pre-rendered images — page images are rendered on-demand at query time
            self.db.collection("users").document(uid).collection("personal_files").document(file_id).update({
                "status": "indexed",
                "chunk_count": chunk_count,
                "indexed_at": firestore.SERVER_TIMESTAMP,
                "gcs_text": text_uri,
                "gcs_original": f"gs://{PERSONAL_BUCKET}/{uid}/{file_id}.original",
                "content_type": content_type,
            })

            return {
                "file_id": file_id,
                "filename": filename,
                "status": "indexed",
                "size_bytes": len(file_bytes),
                "chunk_count": chunk_count,
            }

        except ValueError as e:
            # Validation errors (quota, duplicate, extraction failures) — re-raise as-is
            self.db.collection("users").document(uid).collection("personal_files").document(file_id).update({
                "status": "failed",
                "error": str(e)[:500],
            })
            raise
        except Exception as e:
            # Unexpected errors — mark as failed and wrap in RuntimeError
            error_msg = f"Processing failed: {str(e)[:400]}"
            self.db.collection("users").document(uid).collection("personal_files").document(file_id).update({
                "status": "failed",
                "error": error_msg[:500],
            })
            raise RuntimeError(error_msg) from e

    def _index_to_corpus(self, text_uri: str) -> int:
        """Index a text file into the personal RAG corpus. Returns estimated chunk count."""
        url = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/{self.corpus_name}/ragFiles:import"

        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
        }

        payload = {
            "importRagFilesConfig": {
                "gcsSource": {"uris": [text_uri]},
                "ragFileChunkingConfig": {
                    "chunkSize": 1024,
                    "chunkOverlap": 200,
                },
            }
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code != 200:
            raise Exception(f"RAG indexing failed: {resp.status_code} - {resp.text[:300]}")

        # The import is async — we get an operation name back
        result = resp.json()
        operation_name = result.get("name", "")

        # Poll for completion (up to 30s)
        for _ in range(15):
            time.sleep(2)
            op_resp = requests.get(
                f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/{operation_name}",
                headers={"Authorization": f"Bearer {self._get_access_token()}"},
                timeout=10,
            )
            if op_resp.status_code == 200:
                op_data = op_resp.json()
                if op_data.get("done"):
                    if "error" in op_data:
                        raise Exception(f"RAG indexing error: {op_data['error'].get('message', 'Unknown')}")
                    # Extract chunk count from response metadata if available
                    metadata = op_data.get("metadata", {})
                    imported = metadata.get("importRagFilesResults", {}).get("importedRagFilesCount", 0)
                    return max(imported, 1)  # At least 1 if success

        # If we get here, assume it's still processing but will complete
        return 0

    # ─── List Files ───────────────────────────────────────────────────────

    def list_files(self, uid: str) -> list:
        """List all personal files for a user"""
        files_ref = self.db.collection("users").document(uid).collection("personal_files")
        docs = files_ref.order_by("uploaded_at", direction=firestore.Query.DESCENDING).stream()

        files = []
        for doc in docs:
            data = doc.to_dict()
            files.append({
                "file_id": data.get("file_id"),
                "filename": data.get("filename"),
                "status": data.get("status"),
                "error": data.get("error"),
                "content_type": data.get("content_type"),
                "size_bytes": data.get("size_bytes", 0),
                "chunk_count": data.get("chunk_count", 0),
                "uploaded_at": data.get("uploaded_at").isoformat() if data.get("uploaded_at") else None,
            })
        return files

    # ─── Delete File ──────────────────────────────────────────────────────

    def delete_file(self, uid: str, file_id: str) -> bool:
        """Delete a personal file: GCS objects, RAG corpus entry, and Firestore doc"""
        # Verify ownership
        doc_ref = self.db.collection("users").document(uid).collection("personal_files").document(file_id)
        doc = doc_ref.get()
        if not doc.exists:
            return False

        data = doc.to_dict()

        # 1. Delete from RAG corpus (by GCS URI)
        text_uri = data.get("gcs_text")
        if text_uri:
            try:
                self._delete_from_corpus(text_uri)
            except Exception as e:
                print(f"Warning: failed to delete from RAG corpus: {e}")

        # 2. Delete GCS objects
        for suffix in [".original", ".txt"]:
            try:
                blob = self.bucket.blob(f"{uid}/{file_id}{suffix}")
                blob.delete()
            except Exception:
                pass  # OK if already gone

        # 2b. Delete page images
        for img in data.get("images", []):
            try:
                gcs_uri = img.get("gcs_uri", "")
                if gcs_uri:
                    blob_path = gcs_uri.replace(f"gs://{PERSONAL_BUCKET}/", "")
                    self.bucket.blob(blob_path).delete()
            except Exception:
                pass

        # 3. Delete Firestore doc
        doc_ref.delete()
        return True

    def _delete_from_corpus(self, text_uri: str):
        """Delete a file from the RAG corpus by its GCS URI"""
        # List RAG files to find the one matching this URI
        url = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/{self.corpus_name}/ragFiles"
        headers = {"Authorization": f"Bearer {self._get_access_token()}"}

        resp = requests.get(url, headers=headers, params={"pageSize": 1000}, timeout=15)
        if resp.status_code != 200:
            return

        for rag_file in resp.json().get("ragFiles", []):
            if rag_file.get("gcsSource", {}).get("uris", [None])[0] == text_uri:
                # Found it — delete
                file_name = rag_file["name"]
                del_resp = requests.delete(
                    f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/{file_name}",
                    headers=headers,
                    timeout=15,
                )
                if del_resp.status_code == 200:
                    print(f"Deleted RAG file: {file_name}")
                return

    # ─── Signed URL ──────────────────────────────────────────────────────

    def get_signed_url(self, uid: str, file_id: str, expiration_minutes: int = 60) -> str:
        """Generate a signed URL for the original uploaded file."""
        import datetime
        from google.auth import iam as auth_iam
        from google.oauth2 import service_account as oauth2_sa

        doc = self.db.collection("users").document(uid).collection("personal_files").document(file_id).get()
        if not doc.exists:
            raise FileNotFoundError(f"File {file_id} not found")

        data = doc.to_dict()
        content_type = data.get("content_type", "application/octet-stream")
        filename = data.get("filename", file_id)

        blob = self.bucket.blob(f"{uid}/{file_id}.original")
        if not blob.exists():
            raise FileNotFoundError(f"Original file not found in GCS")

        # Build signing credentials from compute-engine credentials (Cloud Run)
        credentials, project = google.auth.default()
        if not hasattr(credentials, "service_account_email"):
            credentials.refresh(google.auth.transport.requests.Request())
        sa_email = getattr(credentials, "service_account_email", None) or f"{PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

        signer = auth_iam.Signer(
            request=google.auth.transport.requests.Request(),
            credentials=credentials,
            service_account_email=sa_email,
        )
        signing_creds = oauth2_sa.Credentials(
            signer=signer,
            service_account_email=sa_email,
            token_uri="https://oauth2.googleapis.com/token",
            project_id=project or PROJECT_ID,
        )

        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=expiration_minutes),
            method="GET",
            credentials=signing_creds,
            response_type=content_type,
            response_disposition=f'inline; filename="{filename}"',
        )
        return url

    # ─── Delete All User Files ────────────────────────────────────────────

    def delete_all_files(self, uid: str) -> int:
        """Delete all personal files for a user. Returns count deleted."""
        files = self.list_files(uid)
        count = 0
        for f in files:
            if self.delete_file(uid, f["file_id"]):
                count += 1
        return count
