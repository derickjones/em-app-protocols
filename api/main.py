"""
EM Protocol RAG API
FastAPI backend for querying emergency medicine protocols
"""

from fastapi import FastAPI, HTTPException, Query
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
            citations=[
                Citation(
                    protocol_id=c["source"].split("/")[-1].replace(".txt", ""),
                    source_uri=c["source"],
                    relevance_score=c["score"]
                )
                for c in result.get("citations", [])
            ],
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
    """Response with signed upload URL"""
    upload_url: str
    gcs_path: str
    expires_in: int

@app.post("/upload-url", response_model=UploadURLResponse)
async def get_upload_url(request: UploadURLRequest):
    """
    Generate a signed URL for uploading a PDF to GCS.
    The upload will trigger the Cloud Function to process the PDF.
    """
    from google.cloud import storage
    from datetime import timedelta
    
    try:
        # Sanitize filename
        safe_filename = request.filename.replace(" ", "_")
        if not safe_filename.lower().endswith(".pdf"):
            safe_filename += ".pdf"
        
        # GCS path in the raw protocols bucket (triggers Cloud Function)
        bucket_name = "clinical-assistant-457902-protocols-raw"
        blob_path = f"{request.org_id}/{safe_filename}"
        
        # Generate signed URL
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=15),
            method="PUT",
            content_type="application/pdf",
        )
        
        return UploadURLResponse(
            upload_url=url,
            gcs_path=f"gs://{bucket_name}/{blob_path}",
            expires_in=900  # 15 minutes in seconds
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate upload URL: {str(e)}")


# Run with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
