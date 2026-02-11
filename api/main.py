"""
EM Protocol RAG API
FastAPI backend for querying emergency medicine protocols
"""

import os
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import time
import requests
import google.auth
import google.auth.transport.requests
from google.cloud import storage

from rag_service import RAGService
from protocol_service import ProtocolService
from auth_service import get_current_user, get_verified_user, get_optional_user, UserProfile, require_ed_access, require_admin, verify_firebase_token, check_email_verified

# RAG Configuration
PROJECT_NUMBER = os.environ.get("PROJECT_NUMBER", "930035889332")
RAG_LOCATION = os.environ.get("RAG_LOCATION", "us-west4")
CORPUS_ID = os.environ.get("CORPUS_ID", "2305843009213693952")

# Initialize FastAPI app
app = FastAPI(
    title="EM Protocol RAG API",
    description="AI-powered emergency medicine protocol search",
    version="1.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
rag_service = RAGService()
protocol_service = ProtocolService()


def get_access_token():
    """Get OAuth2 access token for REST API calls"""
    credentials, _ = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token


def delete_from_rag_corpus(org_id: str, protocol_id: str) -> bool:
    """
    Delete a file from the RAG corpus by finding and removing it.
    Returns True if found and deleted, False otherwise.
    """
    corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{CORPUS_ID}"
    
    # List all RAG files to find the one to delete
    url = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/{corpus_name}/ragFiles"
    headers = {"Authorization": f"Bearer {get_access_token()}"}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Failed to list RAG files: {response.status_code}")
            return False
        
        rag_files = response.json().get("ragFiles", [])
        
        # Find files matching this org_id/protocol_id
        # The source URI should contain the path
        target_path = f"{org_id}/{protocol_id}"
        deleted_count = 0
        
        for rag_file in rag_files:
            file_name = rag_file.get("name", "")
            # Check if this file matches by examining the gcsSource or displayName
            gcs_source = rag_file.get("gcsSource", {}).get("uris", [])
            
            # Check if any URI contains our target path
            matches = any(target_path in uri for uri in gcs_source)
            
            if not matches:
                # Also check by display name pattern
                display_name = rag_file.get("displayName", "")
                if display_name == "extracted_text.txt" or display_name == f"{protocol_id}.txt":
                    # Need to get more details about this file
                    detail_response = requests.get(
                        f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/{file_name}",
                        headers=headers
                    )
                    if detail_response.status_code == 200:
                        file_detail = detail_response.json()
                        source_uri = file_detail.get("ragFileConfig", {}).get("ragFileSource", {}).get("gcsSource", {}).get("uri", "")
                        if target_path in source_uri:
                            matches = True
            
            if matches:
                # Delete this RAG file
                delete_url = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/{file_name}"
                delete_response = requests.delete(delete_url, headers=headers)
                if delete_response.status_code == 200:
                    print(f"Deleted RAG file: {file_name}")
                    deleted_count += 1
                else:
                    print(f"Failed to delete RAG file: {delete_response.status_code}")
        
        return deleted_count > 0
        
    except Exception as e:
        print(f"Error deleting from RAG corpus: {e}")
        return False


# ----- Request/Response Models -----

class QueryRequest(BaseModel):
    """Request model for protocol queries"""
    query: str = Field(..., description="The question to ask", min_length=3, max_length=500)
    ed_ids: List[str] = Field(default=[], description="ED IDs to search within (empty = all user's EDs)")
    bundle_ids: List[str] = Field(default=["all"], description="Bundle IDs to search, or ['all'] for all bundles")
    include_images: bool = Field(default=True, description="Include relevant images in response")
    sources: List[str] = Field(default=["local", "wikem"], description="Sources to search: 'local' (department protocols), 'wikem' (general ED reference)")
    enterprise_id: Optional[str] = Field(default=None, description="Enterprise ID override (super_admin only)")

class ImageInfo(BaseModel):
    """Image information in query response"""
    page: int
    url: str
    protocol_id: str

class Citation(BaseModel):
    """Citation information"""
    protocol_id: str
    source_uri: str
    relevance_score: float
    source_type: str = "local"  # "local" or "wikem"

class QueryResponse(BaseModel):
    """Response model for protocol queries"""
    answer: str
    images: List[ImageInfo]
    citations: List[Citation]
    query_time_ms: int
    
class ProtocolInfo(BaseModel):
    """Protocol metadata"""
    protocol_id: str
    org_id: str
    page_count: int
    char_count: int
    image_count: int
    confidence: float
    text_uri: str

class ProtocolListResponse(BaseModel):
    """Response for listing protocols"""
    protocols: List[ProtocolInfo]
    count: int

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    rag_corpus: str

class UserProfileResponse(BaseModel):
    """User profile response"""
    uid: str
    email: str
    enterpriseId: Optional[str]
    enterpriseName: Optional[str]
    role: str
    edAccess: List[str]


# ----- Endpoints -----

@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint with API info"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        rag_corpus=rag_service.corpus_name
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        rag_corpus=rag_service.corpus_name
    )


# ----- Auth Endpoints -----

@app.get("/auth/me", response_model=UserProfileResponse)
async def get_current_user_profile(user: UserProfile = Depends(get_current_user)):
    """
    Get current user's profile
    Creates user if first login with valid domain
    """
    return UserProfileResponse(**user.to_dict())


@app.get("/enterprise")
async def get_user_enterprise(user: UserProfile = Depends(get_current_user)):
    """
    Get the current user's enterprise with all EDs and their bundles.
    Returns the full hierarchy for the frontend to populate selectors.
    
    For super_admin users with no enterprise_id, returns ALL enterprises
    so they can switch between them.
    """
    from google.cloud import firestore as fs
    db_client = fs.Client(project="clinical-assistant-457902")
    
    # Super admin with no enterprise - return all enterprises
    if not user.enterprise_id and user.role == "super_admin":
        try:
            all_enterprises = []
            for ent_doc in db_client.collection("enterprises").stream():
                ent_data = ent_doc.to_dict()
                eds = []
                for ed_doc in ent_doc.reference.collection("eds").stream():
                    ed_data = ed_doc.to_dict()
                    ed_data["id"] = ed_doc.id
                    bundles = []
                    for bundle_doc in ed_doc.reference.collection("bundles").stream():
                        bundle_data = bundle_doc.to_dict()
                        bundle_data["id"] = bundle_doc.id
                        bundles.append(bundle_data)
                    ed_data["bundles"] = bundles
                    eds.append(ed_data)
                all_enterprises.append({
                    "id": ent_doc.id,
                    "name": ent_data.get("name", ""),
                    "eds": eds,
                })
            
            # Return first enterprise as primary, but include all in response
            if not all_enterprises:
                raise HTTPException(status_code=404, detail="No enterprises found")
            
            primary = all_enterprises[0]
            return {
                "id": primary["id"],
                "name": primary["name"],
                "eds": primary["eds"],
                "userEdAccess": [ed["id"] for ed in primary["eds"]],
                "userRole": user.role,
                "allEnterprises": all_enterprises
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    if not user.enterprise_id:
        raise HTTPException(status_code=404, detail="No enterprise associated with this user")
    
    try:
        # Get enterprise doc
        enterprise_ref = db_client.collection("enterprises").document(user.enterprise_id)
        enterprise_doc = enterprise_ref.get()
        
        if not enterprise_doc.exists:
            raise HTTPException(status_code=404, detail="Enterprise not found")
        
        enterprise_data = enterprise_doc.to_dict()
        
        # Get all EDs under this enterprise
        eds = []
        eds_ref = enterprise_ref.collection("eds")
        for ed_doc in eds_ref.stream():
            ed_data = ed_doc.to_dict()
            ed_data["id"] = ed_doc.id
            
            # Get bundles for this ED
            bundles = []
            bundles_ref = eds_ref.document(ed_doc.id).collection("bundles")
            for bundle_doc in bundles_ref.stream():
                bundle_data = bundle_doc.to_dict()
                bundle_data["id"] = bundle_doc.id
                bundles.append(bundle_data)
            
            ed_data["bundles"] = bundles
            eds.append(ed_data)
        
        return {
            "id": user.enterprise_id,
            "name": enterprise_data.get("name", ""),
            "eds": eds,
            "userEdAccess": user.ed_access,
            "userRole": user.role
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----- Query Endpoints -----

@app.post("/query", response_model=QueryResponse)
async def query_protocols(
    request: QueryRequest,
    user: Optional[UserProfile] = Depends(get_verified_user)
):
    """
    Query protocols with AI-powered search
    
    Returns an answer with citations and relevant images.
    Requires authentication AND verified email for org-scoped queries.
    """
    start_time = time.time()
    
    try:
        # Determine which EDs to search
        ed_ids = request.ed_ids if request.ed_ids else (user.ed_access if user else [])
        enterprise_id = user.enterprise_id if user else None
        
        # Super admin can override enterprise_id from request body
        if user and user.role == "super_admin" and not enterprise_id and request.enterprise_id:
            enterprise_id = request.enterprise_id
        
        # Get RAG results with ED/bundle filtering
        result = rag_service.query(
            query=request.query,
            include_images=request.include_images,
            sources=request.sources,
            enterprise_id=enterprise_id,
            ed_ids=ed_ids,
            bundle_ids=request.bundle_ids
        )
        
        query_time_ms = int((time.time() - start_time) * 1000)
        
        # Build deduplicated citations with PDF URLs
        seen_protocols = set()
        citations = []
        for c in result.get("citations", []):
            source = c["source"]
            source_type = c.get("source_type", "local")
            
            # Handle WikEM citations
            if source_type == "wikem":
                # Source is like: gs://clinical-assistant-457902-wikem/processed/Hyponatremia.md
                parts = source.replace("gs://", "").split("/")
                # Get the filename without extension as the topic name
                filename = parts[-1] if parts else "unknown"
                topic_id = filename.replace(".md", "")
                
                wikem_key = f"wikem-{topic_id}"
                if wikem_key in seen_protocols:
                    continue
                seen_protocols.add(wikem_key)
                
                citations.append(Citation(
                    protocol_id=topic_id,
                    source_uri=f"https://wikem.org/wiki/{topic_id}",
                    relevance_score=c["score"],
                    source_type="wikem"
                ))
                continue
            
            # Handle local protocol citations
            # Extract protocol info from path like:
            # gs://bucket/enterprise_id/ed_id/bundle_id/protocol_id/extracted_text.txt
            parts = source.replace("gs://", "").split("/")
            
            # Skip legacy rag-input files (no longer exist)
            if "rag-input" in source:
                continue
            
            if len(parts) >= 6:
                # New format: bucket/enterprise_id/ed_id/bundle_id/protocol_id/extracted_text.txt
                enterprise_id_part = parts[1]
                ed_id_part = parts[2]
                bundle_id = parts[3]
                protocol_id = parts[4]
            elif len(parts) >= 5:
                # Legacy format: bucket/org_id/bundle_id/protocol_id/extracted_text.txt
                enterprise_id_part = parts[1]
                ed_id_part = None
                bundle_id = parts[2]
                protocol_id = parts[3]
            else:
                continue
            
            # Skip duplicates and extracted_text entries
            if protocol_id in seen_protocols or protocol_id == "extracted_text":
                continue
            seen_protocols.add(protocol_id)
            
            # Build public PDF URL
            if ed_id_part:
                pdf_url = f"https://storage.googleapis.com/clinical-assistant-457902-protocols-raw/{enterprise_id_part}/{ed_id_part}/{bundle_id}/{protocol_id}.pdf"
            else:
                pdf_url = f"https://storage.googleapis.com/clinical-assistant-457902-protocols-raw/{enterprise_id_part}/{bundle_id}/{protocol_id}.pdf"
            
            citations.append(Citation(
                protocol_id=protocol_id,
                source_uri=pdf_url,
                relevance_score=c["score"],
                source_type="local"
            ))
        
        return QueryResponse(
            answer=result["answer"],
            images=[
                ImageInfo(
                    page=img["page"],
                    url=img["url"],
                    protocol_id=img["source"]
                )
                for img in result.get("images", [])
            ],
            citations=citations,
            query_time_ms=query_time_ms
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/protocols", response_model=ProtocolListResponse)
async def list_protocols(
    enterprise_id: str = Query(default="mayo-clinic", description="Enterprise ID"),
    ed_id: str = Query(default=None, description="ED ID"),
    bundle_id: str = Query(default=None, description="Bundle ID")
):
    """
    List all protocols for an enterprise, optionally filtered by ED and bundle
    """
    try:
        protocols = protocol_service.list_protocols(enterprise_id, ed_id, bundle_id)
        
        return ProtocolListResponse(
            protocols=[
                ProtocolInfo(
                    protocol_id=p.get("protocol_id", "unknown"),
                    org_id=p.get("org_id", enterprise_id),
                    page_count=p.get("page_count", 0),
                    char_count=p.get("char_count", 0),
                    image_count=p.get("image_count", 0),
                    confidence=p.get("confidence", 0.0),
                    text_uri=p.get("text_uri", "")
                )
                for p in protocols
            ],
            count=len(protocols)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/hospitals")
async def list_all_hospitals():
    """
    List all enterprises with their EDs, bundles, and protocols.
    Returns hierarchical structure: { enterprises: { enterprise: { ed: { bundle: [protocols] } } } }
    Also available at /enterprises for the new naming.
    """
    try:
        enterprises = protocol_service.list_all_enterprises()
        return {"hospitals": enterprises, "enterprises": enterprises}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/enterprises")
async def list_all_enterprises():
    """
    List all enterprises with their EDs, bundles, and protocols.
    Returns hierarchical structure: { enterprises: { enterprise: { ed: { bundle: [protocols] } } } }
    """
    try:
        enterprises = protocol_service.list_all_enterprises()
        return {"enterprises": enterprises}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/protocols/{enterprise_id}/{ed_id}/{bundle_id}/{protocol_id}")
async def delete_protocol(enterprise_id: str, ed_id: str, bundle_id: str, protocol_id: str):
    """
    Delete a protocol from the system.
    Removes from processed bucket, raw bucket, and RAG corpus.
    """
    try:
        # Delete from processed bucket
        success = protocol_service.delete_protocol(enterprise_id, ed_id, bundle_id, protocol_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Protocol not found")
        
        # Also delete from raw bucket
        raw_bucket = f"clinical-assistant-457902-protocols-raw"
        storage_client = storage.Client()
        bucket = storage_client.bucket(raw_bucket)
        
        # Try to delete the PDF (could be .pdf or other extensions)
        for ext in [".pdf", ".PDF"]:
            blob = bucket.blob(f"{enterprise_id}/{ed_id}/{bundle_id}/{protocol_id}{ext}")
            if blob.exists():
                blob.delete()
                break
        
        # Delete from RAG corpus
        rag_deleted = delete_from_rag_corpus(enterprise_id, protocol_id)
        
        return {
            "status": "deleted", 
            "protocol_id": protocol_id, 
            "enterprise_id": enterprise_id,
            "ed_id": ed_id,
            "bundle_id": bundle_id,
            "rag_removed": rag_deleted
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/reindex-rag")
async def reindex_rag_corpus():
    """
    Admin endpoint: Clear and re-index all protocols in the RAG corpus.
    This finds all extracted_text.txt files in the processed bucket and indexes them.
    """
    try:
        corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{CORPUS_ID}"
        headers = {"Authorization": f"Bearer {get_access_token()}"}
        
        # Step 1: Delete all existing RAG files
        list_url = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/{corpus_name}/ragFiles"
        response = requests.get(list_url, headers=headers)
        
        deleted_count = 0
        if response.status_code == 200:
            rag_files = response.json().get("ragFiles", [])
            for rag_file in rag_files:
                file_name = rag_file.get("name", "")
                delete_response = requests.delete(
                    f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/{file_name}",
                    headers=headers
                )
                if delete_response.status_code == 200:
                    deleted_count += 1
        
        # Step 2: Find all current extracted_text.txt files
        storage_client = storage.Client()
        bucket = storage_client.bucket("clinical-assistant-457902-protocols-processed")
        
        text_files = []
        for blob in bucket.list_blobs():
            if blob.name.endswith("extracted_text.txt"):
                text_files.append(f"gs://clinical-assistant-457902-protocols-processed/{blob.name}")
        
        if not text_files:
            return {
                "status": "completed",
                "deleted": deleted_count,
                "indexed": 0,
                "message": "No extracted text files found to index"
            }
        
        # Step 3: Batch import all files (max 25 per request)
        BATCH_SIZE = 25
        operations = []
        
        for i in range(0, len(text_files), BATCH_SIZE):
            batch = text_files[i:i + BATCH_SIZE]
            import_url = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/{corpus_name}/ragFiles:import"
            payload = {
                "importRagFilesConfig": {
                    "gcsSource": {
                        "uris": batch
                    },
                    "ragFileChunkingConfig": {
                        "chunkSize": 1024,
                        "chunkOverlap": 200
                    }
                }
            }
            
            import_response = requests.post(import_url, headers=headers, json=payload)
            
            if import_response.status_code == 200:
                operation = import_response.json().get("name", "")
                if operation:
                    operations.append(operation)
            else:
                print(f"Batch import failed for batch {i//BATCH_SIZE + 1}: {import_response.text}")
        
        if operations:
            return {
                "status": "indexing_started",
                "deleted": deleted_count,
                "files_to_index": len(text_files),
                "operation": operations[-1],  # Track last operation for polling
                "batches": len(operations),
                "message": f"Cleared {deleted_count} old files, started indexing {len(text_files)} files in {len(operations)} batch(es)"
            }
        else:
            return {
                "status": "error",
                "deleted": deleted_count,
                "files_to_index": len(text_files),
                "message": "Failed to start indexing — all batches failed"
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/reindex-rag/status")
async def check_reindex_status(operation: str = Query(..., description="Operation name from reindex response")):
    """
    Check the status of a RAG reindex operation.
    Returns whether it's still running, completed, or failed.
    """
    try:
        headers = {"Authorization": f"Bearer {get_access_token()}"}
        
        # Poll the long-running operation
        status_url = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/{operation}"
        response = requests.get(status_url, headers=headers)
        
        if response.status_code != 200:
            return {"done": False, "status": "unknown", "message": "Could not check operation status"}
        
        data = response.json()
        done = data.get("done", False)
        
        if done:
            # Check for errors
            error = data.get("error")
            if error:
                return {
                    "done": True,
                    "status": "error",
                    "message": f"Indexing failed: {error.get('message', 'Unknown error')}"
                }
            
            # Success - get result details
            result = data.get("response", {})
            imported = result.get("importedRagFilesCount", 0)
            failed = result.get("failedRagFilesCount", 0)
            skipped = result.get("skippedRagFilesCount", 0)
            
            return {
                "done": True,
                "status": "completed",
                "message": f"Indexing complete: {imported} files indexed, {failed} failed, {skipped} skipped",
                "imported": imported,
                "failed": failed,
                "skipped": skipped
            }
        else:
            # Still in progress
            metadata = data.get("metadata", {})
            progress = metadata.get("genericMetadata", {}).get("partialFailures", [])
            return {
                "done": False,
                "status": "in_progress",
                "message": "Indexing in progress..."
            }
    
    except Exception as e:
        return {"done": False, "status": "error", "message": str(e)}


@app.get("/protocols/{enterprise_id}/{ed_id}/{bundle_id}/{protocol_id}")
async def get_protocol(enterprise_id: str, ed_id: str, bundle_id: str, protocol_id: str):
    """
    Get details for a specific protocol
    """
    try:
        protocol = protocol_service.get_protocol(enterprise_id, ed_id, bundle_id, protocol_id)
        
        if not protocol:
            raise HTTPException(status_code=404, detail="Protocol not found")
        
        return protocol
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/protocols/{enterprise_id}/{ed_id}/{bundle_id}/{protocol_id}/images")
async def get_protocol_images(enterprise_id: str, ed_id: str, bundle_id: str, protocol_id: str):
    """
    Get images for a specific protocol
    """
    try:
        images = protocol_service.get_protocol_images(enterprise_id, ed_id, bundle_id, protocol_id)
        return {"images": images, "count": len(images)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class UploadURLRequest(BaseModel):
    """Request for generating upload URL"""
    enterprise_id: str = Field(..., description="Enterprise ID")
    ed_id: str = Field(..., description="ED ID")
    bundle_id: str = Field(..., description="Bundle ID")
    filename: str = Field(..., description="PDF filename")

class UploadURLResponse(BaseModel):
    """Response with upload info"""
    upload_url: str
    gcs_path: str
    method: str

@app.post("/upload-url", response_model=UploadURLResponse)
async def get_upload_url(request: UploadURLRequest, http_request: Request):
    """
    Returns the API endpoint for uploading PDFs.
    Upload PDFs via POST to /upload with multipart form data.
    """
    # Sanitize filename
    safe_filename = request.filename.replace(" ", "_")
    if not safe_filename.lower().endswith(".pdf"):
        safe_filename += ".pdf"
    
    gcs_path = f"gs://clinical-assistant-457902-protocols-raw/{request.enterprise_id}/{request.ed_id}/{request.bundle_id}/{safe_filename}"
    
    # Get base URL from request
    base_url = str(http_request.base_url).rstrip('/')
    
    return UploadURLResponse(
        upload_url=f"{base_url}/upload",
        gcs_path=gcs_path,
        method="POST multipart/form-data with 'file', 'enterprise_id', 'ed_id', and 'bundle_id' fields"
    )


@app.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    enterprise_id: str = Form(...),
    ed_id: str = Form(...),
    bundle_id: str = Form(...)
):
    """
    Upload a PDF protocol directly.
    The file will be saved to GCS and trigger processing.
    """
    from google.cloud import storage
    
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        # Sanitize filename
        safe_filename = file.filename.replace(" ", "_")
        
        # Upload to GCS (triggers Cloud Function)
        bucket_name = "clinical-assistant-457902-protocols-raw"
        blob_path = f"{enterprise_id}/{ed_id}/{bundle_id}/{safe_filename}"
        
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        # Read file content
        content = await file.read()
        blob.upload_from_string(content, content_type="application/pdf")
        
        return {
            "status": "success",
            "message": "PDF uploaded successfully. Processing will begin shortly.",
            "gcs_path": f"gs://{bucket_name}/{blob_path}",
            "protocol_id": safe_filename.replace(".pdf", "").replace(".PDF", "")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


class UploadFromURLRequest(BaseModel):
    """Request to upload a PDF from a URL"""
    url: str = Field(..., description="URL of the PDF to download")
    enterprise_id: str = Field(..., description="Enterprise ID")
    ed_id: str = Field(..., description="ED ID")
    bundle_id: str = Field(..., description="Bundle ID")
    filename: Optional[str] = Field(default=None, description="Override filename (optional)")


@app.post("/upload-from-url")
async def upload_pdf_from_url(request: UploadFromURLRequest):
    """
    Upload a PDF by providing a URL. The server fetches the file and saves it to GCS.
    Useful for corporate environments where local file access is restricted.
    """
    from google.cloud import storage
    import re

    try:
        # Fetch the PDF from the URL
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; EMProtocols/1.0)"
        }
        response = requests.get(request.url, headers=headers, timeout=60, stream=True)

        if response.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to download file from URL (HTTP {response.status_code})"
            )

        # Check content type
        content_type = response.headers.get("content-type", "")
        if "pdf" not in content_type.lower() and not request.url.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"URL does not appear to be a PDF (content-type: {content_type})"
            )

        # Check file size (max 50MB)
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large (max 50MB)")

        content = response.content

        # Determine filename
        if request.filename:
            filename = request.filename
        else:
            # Try to extract from URL or Content-Disposition
            cd = response.headers.get("content-disposition", "")
            cd_match = re.search(r'filename[^;=\n]*=(["\']?)(.+?)\1(;|$)', cd)
            if cd_match:
                filename = cd_match.group(2)
            else:
                # Extract from URL path
                url_path = request.url.split("?")[0].split("#")[0]
                filename = url_path.split("/")[-1]

            if not filename or filename == "":
                filename = "downloaded_protocol.pdf"

        # Ensure .pdf extension
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"

        # Sanitize filename
        safe_filename = filename.replace(" ", "_")
        safe_filename = re.sub(r'[^\w\-.]', '_', safe_filename)

        # Upload to GCS
        bucket_name = "clinical-assistant-457902-protocols-raw"
        blob_path = f"{request.enterprise_id}/{request.ed_id}/{request.bundle_id}/{safe_filename}"

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        blob.upload_from_string(content, content_type="application/pdf")

        return {
            "status": "success",
            "message": f"PDF '{safe_filename}' uploaded successfully from URL. Processing will begin shortly.",
            "gcs_path": f"gs://{bucket_name}/{blob_path}",
            "protocol_id": safe_filename.replace(".pdf", "").replace(".PDF", ""),
            "filename": safe_filename,
            "size_bytes": len(content),
        }

    except HTTPException:
        raise
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=408, detail="URL download timed out (60s limit)")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=400, detail="Could not connect to the provided URL")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload from URL failed: {str(e)}")


# ============================================================================
# ADMIN MANAGEMENT ENDPOINTS
# ============================================================================

from google.cloud import firestore
db = firestore.Client(project="clinical-assistant-457902")


class AdminUser(BaseModel):
    """Admin user data model"""
    email: str
    enterprise_id: Optional[str] = ""
    role: str = "admin"
    ed_access: List[str] = []


class AdminUserResponse(BaseModel):
    """Response model for admin user"""
    uid: str
    email: str
    role: str
    edAccess: List[str]
    enterpriseId: Optional[str] = None
    createdAt: str


@app.get("/admin/users")
async def list_admin_users(
    enterprise_id: Optional[str] = Query(None),
    user: UserProfile = Depends(get_current_user)
):
    """
    List all admin users (super_admin only)
    Optionally filter by enterprise_id
    """
    if user.role not in ["super_admin"]:
        raise HTTPException(status_code=403, detail="Only super admins can view admin users")
    
    try:
        users_ref = db.collection("users")
        
        # Filter by enterprise if provided
        if enterprise_id:
            query = users_ref.where("enterprise_id", "==", enterprise_id)
        else:
            query = users_ref
        
        users = []
        for doc in query.stream():
            user_data = doc.to_dict()
            users.append({
                "uid": doc.id,
                "email": user_data.get("email", ""),
                "role": user_data.get("role", "user"),
                "edAccess": user_data.get("ed_access", []),
                "enterpriseId": user_data.get("enterprise_id", ""),
                "createdAt": user_data.get("createdAt", ""),
            })
        
        return {"users": users}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list users: {str(e)}")


@app.post("/admin/users")
async def create_admin_user(
    admin_data: AdminUser,
    user: UserProfile = Depends(get_current_user)
):
    """
    Create or update an admin user (super_admin only)
    """
    if user.role not in ["super_admin"]:
        raise HTTPException(status_code=403, detail="Only super admins can create admin users")
    
    try:
        # Check if user exists by email
        users_ref = db.collection("users")
        query = users_ref.where("email", "==", admin_data.email).limit(1)
        existing = list(query.stream())
        
        # For super_admin, clear enterprise association
        if admin_data.role == "super_admin":
            user_data = {
                "email": admin_data.email,
                "enterprise_id": None,
                "role": "super_admin",
                "ed_access": [],
                "updatedAt": firestore.SERVER_TIMESTAMP,
            }
        else:
            user_data = {
                "email": admin_data.email,
                "enterprise_id": admin_data.enterprise_id,
                "role": admin_data.role,
                "ed_access": admin_data.ed_access,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            }
        
        if existing:
            # Update existing user
            doc_ref = existing[0].reference
            doc_ref.update(user_data)
            return {"status": "updated", "uid": existing[0].id}
        else:
            # Create new user record
            user_data["createdAt"] = firestore.SERVER_TIMESTAMP
            doc_ref = users_ref.document()
            doc_ref.set(user_data)
            return {"status": "created", "uid": doc_ref.id}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")


@app.delete("/admin/users/{uid}")
async def delete_admin_user(
    uid: str,
    user: UserProfile = Depends(get_current_user)
):
    """
    Delete an admin user (super_admin only)
    """
    if user.role not in ["super_admin"]:
        raise HTTPException(status_code=403, detail="Only super admins can delete admin users")
    
    try:
        # Get user to check if they're super_admin (can't delete super_admins)
        user_ref = db.collection("users").document(uid)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_doc.to_dict()
        if user_data.get("role") == "super_admin":
            raise HTTPException(status_code=403, detail="Cannot delete super admin users")
        
        # Delete the user
        user_ref.delete()
        
        return {"status": "deleted", "uid": uid}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")


@app.post("/admin/make-super-admin")
async def make_super_admin(
    email: str = Query(..., description="Email address to make super admin")
):
    """
    Development endpoint to make a user a super admin
    In production, this should be secured or removed
    """
    try:
        users_ref = db.collection("users")
        query = users_ref.where("email", "==", email).limit(1)
        existing = list(query.stream())
        
        if existing:
            # Update existing user - remove org association for super admins
            doc_ref = existing[0].reference
            doc_ref.update({
                "role": "super_admin",
                "orgId": firestore.DELETE_FIELD,  # Remove orgId field
                "orgName": firestore.DELETE_FIELD,  # Remove orgName field
                "bundleAccess": [],
                "updatedAt": firestore.SERVER_TIMESTAMP,
            })
            return {"status": "updated", "email": email, "role": "super_admin"}
        else:
            # Create new super admin user without org
            user_data = {
                "email": email,
                "role": "super_admin",
                "bundleAccess": [],
                "createdAt": firestore.SERVER_TIMESTAMP,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            }
            doc_ref = users_ref.document()
            doc_ref.set(user_data)
            return {"status": "created", "email": email, "role": "super_admin"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to make super admin: {str(e)}")


# ============================================================================
# ENTERPRISE / ED / BUNDLE CRUD ENDPOINTS
# ============================================================================

class CreateEnterprise(BaseModel):
    """Request to create a new enterprise"""
    id: str = Field(..., description="URL-safe enterprise ID (e.g. 'mayo-clinic')")
    name: str = Field(..., description="Display name")
    allowed_domains: List[str] = Field(default=[], description="Allowed email domains for auto-signup")


class CreateED(BaseModel):
    """Request to create a new ED under an enterprise"""
    id: str = Field(..., description="URL-safe ED ID (e.g. 'rochester')")
    name: str = Field(..., description="Display name")
    location: str = Field(default="", description="Location description")


class CreateBundle(BaseModel):
    """Request to create a new bundle under an ED"""
    id: str = Field(..., description="URL-safe bundle ID (e.g. 'acls')")
    name: str = Field(..., description="Display name")
    description: str = Field(default="", description="Bundle description")
    icon: str = Field(default="folder", description="Icon name")
    color: str = Field(default="#3B82F6", description="Hex color")


@app.get("/admin/enterprises")
async def list_all_firestore_enterprises(
    user: UserProfile = Depends(get_current_user)
):
    """
    List all enterprises with EDs and bundles from Firestore.
    Super admin: sees all. Enterprise admin: sees their own.
    """
    if user.role not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        enterprises = []
        enterprises_ref = db.collection("enterprises")
        
        for ent_doc in enterprises_ref.stream():
            # Non-super admins only see their own enterprise
            if user.role != "super_admin" and ent_doc.id != user.enterprise_id:
                continue
            
            ent_data = ent_doc.to_dict()
            ent_data["id"] = ent_doc.id
            
            # Get EDs
            eds = []
            for ed_doc in ent_doc.reference.collection("eds").stream():
                ed_data = ed_doc.to_dict()
                ed_data["id"] = ed_doc.id
                
                # Get bundles
                bundles = []
                for bundle_doc in ed_doc.reference.collection("bundles").stream():
                    bundle_data = bundle_doc.to_dict()
                    bundle_data["id"] = bundle_doc.id
                    bundles.append(bundle_data)
                
                ed_data["bundles"] = bundles
                eds.append(ed_data)
            
            ent_data["eds"] = eds
            enterprises.append(ent_data)
        
        return {"enterprises": enterprises}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list enterprises: {str(e)}")


@app.post("/admin/enterprises")
async def create_enterprise(
    data: CreateEnterprise,
    user: UserProfile = Depends(get_current_user)
):
    """Create a new enterprise (super_admin only)"""
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Only super admins can create enterprises")
    
    try:
        doc_ref = db.collection("enterprises").document(data.id)
        
        # Check if already exists
        if doc_ref.get().exists:
            raise HTTPException(status_code=409, detail=f"Enterprise '{data.id}' already exists")
        
        doc_ref.set({
            "name": data.name,
            "slug": data.id,
            "allowed_domains": data.allowed_domains,
            "subscription_tier": "enterprise",
            "settings": {
                "allow_user_signup": True,
                "max_protocols": 500,
            },
            "createdAt": firestore.SERVER_TIMESTAMP,
        })
        
        return {"status": "created", "id": data.id, "name": data.name}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create enterprise: {str(e)}")


@app.post("/admin/enterprises/{enterprise_id}/eds")
async def create_ed(
    enterprise_id: str,
    data: CreateED,
    user: UserProfile = Depends(get_current_user)
):
    """Create a new ED under an enterprise (super_admin only)"""
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Only super admins can create EDs")
    
    try:
        ent_ref = db.collection("enterprises").document(enterprise_id)
        if not ent_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Enterprise '{enterprise_id}' not found")
        
        ed_ref = ent_ref.collection("eds").document(data.id)
        if ed_ref.get().exists:
            raise HTTPException(status_code=409, detail=f"ED '{data.id}' already exists")
        
        ed_ref.set({
            "name": data.name,
            "slug": data.id,
            "location": data.location,
            "createdAt": firestore.SERVER_TIMESTAMP,
        })
        
        return {"status": "created", "enterprise_id": enterprise_id, "id": data.id, "name": data.name}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create ED: {str(e)}")


@app.post("/admin/enterprises/{enterprise_id}/eds/{ed_id}/bundles")
async def create_bundle(
    enterprise_id: str,
    ed_id: str,
    data: CreateBundle,
    user: UserProfile = Depends(get_current_user)
):
    """Create a new bundle under an ED (super_admin only)"""
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Only super admins can create bundles")
    
    try:
        ent_ref = db.collection("enterprises").document(enterprise_id)
        if not ent_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Enterprise '{enterprise_id}' not found")
        
        ed_ref = ent_ref.collection("eds").document(ed_id)
        if not ed_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"ED '{ed_id}' not found")
        
        bundle_ref = ed_ref.collection("bundles").document(data.id)
        if bundle_ref.get().exists:
            raise HTTPException(status_code=409, detail=f"Bundle '{data.id}' already exists")
        
        bundle_ref.set({
            "name": data.name,
            "slug": data.id,
            "description": data.description,
            "icon": data.icon,
            "color": data.color,
            "createdAt": firestore.SERVER_TIMESTAMP,
        })
        
        return {"status": "created", "enterprise_id": enterprise_id, "ed_id": ed_id, "id": data.id, "name": data.name}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create bundle: {str(e)}")


def _delete_collection(coll_ref):
    """Recursively delete all documents in a collection."""
    for doc in coll_ref.stream():
        # Delete sub-collections first
        for sub_coll in doc.reference.collections():
            _delete_collection(sub_coll)
        doc.reference.delete()


@app.delete("/admin/enterprises/{enterprise_id}/eds/{ed_id}/bundles/{bundle_id}")
async def delete_bundle(
    enterprise_id: str,
    ed_id: str,
    bundle_id: str,
    user: UserProfile = Depends(get_current_user)
):
    """Delete a bundle: removes all GCS files, RAG entries, and Firestore doc (super_admin only)"""
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Only super admins can delete bundles")
    
    try:
        deleted_gcs = 0
        deleted_rag = 0
        
        # Step 1: Delete all files from GCS processed bucket
        storage_client = storage.Client()
        processed_bucket = storage_client.bucket("clinical-assistant-457902-protocols-processed")
        prefix = f"{enterprise_id}/{ed_id}/{bundle_id}/"
        blobs = list(processed_bucket.list_blobs(prefix=prefix))
        for blob in blobs:
            blob.delete()
            deleted_gcs += 1
        
        # Step 2: Delete from GCS raw bucket
        raw_bucket = storage_client.bucket("clinical-assistant-457902-protocols-raw")
        raw_blobs = list(raw_bucket.list_blobs(prefix=prefix))
        for blob in raw_blobs:
            blob.delete()
        
        # Step 3: Delete matching files from RAG corpus
        corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{CORPUS_ID}"
        headers = {"Authorization": f"Bearer {get_access_token()}"}
        list_url = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/{corpus_name}/ragFiles"
        response = requests.get(list_url, headers=headers)
        
        if response.status_code == 200:
            rag_files = response.json().get("ragFiles", [])
            target_path = f"{enterprise_id}/{ed_id}/{bundle_id}/"
            
            for rag_file in rag_files:
                file_name = rag_file.get("name", "")
                gcs_uris = rag_file.get("gcsSource", {}).get("uris", [])
                
                if any(target_path in uri for uri in gcs_uris):
                    delete_url = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/{file_name}"
                    del_resp = requests.delete(delete_url, headers=headers)
                    if del_resp.status_code == 200:
                        deleted_rag += 1
        
        # Step 4: Delete Firestore bundle doc
        bundle_ref = (
            db.collection("enterprises").document(enterprise_id)
            .collection("eds").document(ed_id)
            .collection("bundles").document(bundle_id)
        )
        bundle_ref.delete()
        
        return {
            "status": "deleted",
            "enterprise_id": enterprise_id,
            "ed_id": ed_id,
            "bundle_id": bundle_id,
            "deleted_gcs_files": deleted_gcs,
            "deleted_rag_files": deleted_rag
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete bundle: {str(e)}")


@app.delete("/admin/enterprises/{enterprise_id}/eds/{ed_id}")
async def delete_ed(
    enterprise_id: str,
    ed_id: str,
    user: UserProfile = Depends(get_current_user)
):
    """Delete an ED and all its bundles from Firestore (super_admin only)"""
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Only super admins can delete EDs")
    
    try:
        ed_ref = (
            db.collection("enterprises").document(enterprise_id)
            .collection("eds").document(ed_id)
        )
        
        if not ed_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"ED '{ed_id}' not found")
        
        # Delete all bundles under this ED first
        _delete_collection(ed_ref.collection("bundles"))
        ed_ref.delete()
        
        return {"status": "deleted", "enterprise_id": enterprise_id, "ed_id": ed_id}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete ED: {str(e)}")


@app.delete("/admin/enterprises/{enterprise_id}")
async def delete_enterprise(
    enterprise_id: str,
    user: UserProfile = Depends(get_current_user)
):
    """Delete an enterprise and all its EDs/bundles from Firestore (super_admin only)"""
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Only super admins can delete enterprises")
    
    try:
        ent_ref = db.collection("enterprises").document(enterprise_id)
        
        if not ent_ref.get().exists:
            raise HTTPException(status_code=404, detail=f"Enterprise '{enterprise_id}' not found")
        
        # Delete all EDs (and their bundles) under this enterprise
        for ed_doc in ent_ref.collection("eds").stream():
            _delete_collection(ed_doc.reference.collection("bundles"))
            ed_doc.reference.delete()
        
        ent_ref.delete()
        
        return {"status": "deleted", "enterprise_id": enterprise_id}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete enterprise: {str(e)}")


# Run with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
