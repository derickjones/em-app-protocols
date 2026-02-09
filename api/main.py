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
from auth_service import get_current_user, get_verified_user, get_optional_user, UserProfile, require_bundle_access, verify_firebase_token, check_email_verified

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
    bundle_ids: List[str] = Field(default=["all"], description="Bundle IDs to search, or ['all'] for all bundles")
    include_images: bool = Field(default=True, description="Include relevant images in response")
    sources: List[str] = Field(default=["local", "wikem"], description="Sources to search: 'local' (department protocols), 'wikem' (general ED reference)")

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
    orgId: Optional[str]
    orgName: Optional[str]
    role: str
    bundleAccess: List[str]


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
        # Get RAG results
        result = rag_service.query(
            query=request.query,
            include_images=request.include_images,
            sources=request.sources
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
            # gs://bucket/org_id/bundle_id/protocol_id/extracted_text.txt
            parts = source.replace("gs://", "").split("/")
            
            # Skip legacy rag-input files (no longer exist)
            if "rag-input" in source:
                continue
            
            if len(parts) >= 5:
                # Format: bucket/org_id/bundle_id/protocol_id/extracted_text.txt
                org_id = parts[1]
                bundle_id = parts[2]
                protocol_id = parts[3]
            elif len(parts) >= 4:
                # Legacy format: bucket/org_id/protocol_id/extracted_text.txt
                org_id = parts[1]
                bundle_id = None
                protocol_id = parts[2]
            else:
                continue
            
            # Skip duplicates and extracted_text entries
            if protocol_id in seen_protocols or protocol_id == "extracted_text":
                continue
            seen_protocols.add(protocol_id)
            
            # Build public PDF URL (include bundle if present)
            if bundle_id:
                pdf_url = f"https://storage.googleapis.com/clinical-assistant-457902-protocols-raw/{org_id}/{bundle_id}/{protocol_id}.pdf"
            else:
                pdf_url = f"https://storage.googleapis.com/clinical-assistant-457902-protocols-raw/{org_id}/{protocol_id}.pdf"
            
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
    org_id: str = Query(default="demo-hospital", description="Organization ID")
):
    """
    List all protocols for an organization
    """
    try:
        protocols = protocol_service.list_protocols(org_id)
        
        return ProtocolListResponse(
            protocols=[
                ProtocolInfo(
                    protocol_id=p.get("protocol_id", "unknown"),
                    org_id=p.get("org_id", org_id),
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
    List all hospitals with their bundles and protocols.
    Returns hierarchical structure: { hospitals: { hospital: { bundle: [protocols] } } }
    """
    try:
        hospitals = protocol_service.list_all_hospitals()
        return {"hospitals": hospitals}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/protocols/{org_id}/{protocol_id}")
async def delete_protocol(org_id: str, protocol_id: str):
    """
    Delete a protocol from the system.
    Removes from processed bucket, raw bucket, and RAG corpus.
    """
    try:
        # Delete from processed bucket
        success = protocol_service.delete_protocol(org_id, protocol_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Protocol not found")
        
        # Also delete from raw bucket
        raw_bucket = f"clinical-assistant-457902-protocols-raw"
        storage_client = storage.Client()
        bucket = storage_client.bucket(raw_bucket)
        
        # Try to delete the PDF (could be .pdf or other extensions)
        for ext in [".pdf", ".PDF"]:
            blob = bucket.blob(f"{org_id}/{protocol_id}{ext}")
            if blob.exists():
                blob.delete()
                break
        
        # Delete from RAG corpus
        rag_deleted = delete_from_rag_corpus(org_id, protocol_id)
        
        return {
            "status": "deleted", 
            "protocol_id": protocol_id, 
            "org_id": org_id,
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
        
        # Step 3: Batch import all files
        import_url = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/{corpus_name}/ragFiles:import"
        payload = {
            "importRagFilesConfig": {
                "gcsSource": {
                    "uris": text_files
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
            return {
                "status": "indexing_started",
                "deleted": deleted_count,
                "files_to_index": len(text_files),
                "operation": operation,
                "message": f"Cleared {deleted_count} old files, started indexing {len(text_files)} files"
            }
        else:
            return {
                "status": "error",
                "deleted": deleted_count,
                "error": import_response.text
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/protocols/{org_id}/{protocol_id}")
async def get_protocol(org_id: str, protocol_id: str):
    """
    Get details for a specific protocol
    """
    try:
        protocol = protocol_service.get_protocol(org_id, protocol_id)
        
        if not protocol:
            raise HTTPException(status_code=404, detail="Protocol not found")
        
        return protocol
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/protocols/{org_id}/{protocol_id}/images")
async def get_protocol_images(org_id: str, protocol_id: str):
    """
    Get images for a specific protocol
    """
    try:
        images = protocol_service.get_protocol_images(org_id, protocol_id)
        return {"images": images, "count": len(images)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class UploadURLRequest(BaseModel):
    """Request for generating upload URL"""
    org_id: str = Field(..., description="Organization ID")
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
    
    gcs_path = f"gs://clinical-assistant-457902-protocols-raw/{request.org_id}/{safe_filename}"
    
    # Get base URL from request
    base_url = str(http_request.base_url).rstrip('/')
    
    return UploadURLResponse(
        upload_url=f"{base_url}/upload",
        gcs_path=gcs_path,
        method="POST multipart/form-data with 'file' and 'org_id' fields"
    )


@app.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    org_id: str = Form(...)
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
        blob_path = f"{org_id}/{safe_filename}"
        
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


# ============================================================================
# ADMIN MANAGEMENT ENDPOINTS
# ============================================================================

from google.cloud import firestore
db = firestore.Client(project="clinical-assistant-457902")


class AdminUser(BaseModel):
    """Admin user data model"""
    email: str
    org_id: str
    role: str = "admin"
    bundle_access: List[str] = []


class AdminUserResponse(BaseModel):
    """Response model for admin user"""
    uid: str
    email: str
    role: str
    bundleAccess: List[str]
    createdAt: str


@app.get("/admin/users")
async def list_admin_users(
    org_id: Optional[str] = Query(None),
    user: UserProfile = Depends(get_current_user)
):
    """
    List all admin users (super_admin only)
    Optionally filter by org_id
    """
    if user.role not in ["super_admin"]:
        raise HTTPException(status_code=403, detail="Only super admins can view admin users")
    
    try:
        users_ref = db.collection("users")
        
        # Filter by org if provided
        if org_id:
            query = users_ref.where("orgId", "==", org_id)
        else:
            query = users_ref
        
        users = []
        for doc in query.stream():
            user_data = doc.to_dict()
            users.append({
                "uid": doc.id,
                "email": user_data.get("email", ""),
                "role": user_data.get("role", "user"),
                "bundleAccess": user_data.get("bundleAccess", []),
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
        
        user_data = {
            "email": admin_data.email,
            "orgId": admin_data.org_id,
            "role": admin_data.role,
            "bundleAccess": admin_data.bundle_access,
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


# Run with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
