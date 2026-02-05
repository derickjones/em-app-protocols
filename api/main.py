"""
EM Protocol RAG API
FastAPI backend for querying emergency medicine protocols
"""

import os
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import time

from rag_service import RAGService
from protocol_service import ProtocolService

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


# ----- Request/Response Models -----

class QueryRequest(BaseModel):
    """Request model for protocol queries"""
    query: str = Field(..., description="The question to ask", min_length=3, max_length=500)
    org_id: str = Field(default="demo-hospital", description="Organization ID")
    include_images: bool = Field(default=True, description="Include relevant images in response")

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


@app.post("/query", response_model=QueryResponse)
async def query_protocols(request: QueryRequest):
    """
    Query protocols with AI-powered search
    
    Returns an answer with citations and relevant images.
    """
    start_time = time.time()
    
    try:
        # Get RAG results
        result = rag_service.query(
            query=request.query,
            include_images=request.include_images
        )
        
        query_time_ms = int((time.time() - start_time) * 1000)
        
        # Build deduplicated citations with PDF URLs
        seen_protocols = set()
        citations = []
        for c in result.get("citations", []):
            source = c["source"]
            # Extract protocol info from path like:
            # gs://bucket/org_id/protocol_id/extracted_text.txt or
            # gs://bucket/rag-input/protocol_id.txt
            parts = source.replace("gs://", "").split("/")
            
            if "rag-input" in source:
                # Format: bucket/rag-input/protocol_id.txt
                protocol_id = parts[-1].replace(".txt", "")
                org_id = "demo-hospital"  # Default org for rag-input files
            elif len(parts) >= 4:
                # Format: bucket/org_id/protocol_id/extracted_text.txt
                org_id = parts[1]
                protocol_id = parts[2]
            else:
                continue
            
            # Skip duplicates and extracted_text entries
            if protocol_id in seen_protocols or protocol_id == "extracted_text":
                continue
            seen_protocols.add(protocol_id)
            
            # Build public PDF URL
            pdf_url = f"https://storage.googleapis.com/clinical-assistant-457902-protocols-raw/{org_id}/{protocol_id}.pdf"
            
            citations.append(Citation(
                protocol_id=protocol_id,
                source_uri=pdf_url,
                relevance_score=c["score"]
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


# Run with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
