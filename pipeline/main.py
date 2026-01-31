"""
Cloud Function: PDF Processing Pipeline
Triggers on PDF upload → Document AI extraction → RAG indexing
"""

try:
    import functions_framework
    CLOUD_FUNCTION = True
except ImportError:
    CLOUD_FUNCTION = False
    # Define a dummy decorator for local testing
    class functions_framework:
        @staticmethod
        def cloud_event(func):
            return func

from google.cloud import storage
from google.cloud import documentai_v1 as documentai
import google.auth
import google.auth.transport.requests
import requests
import json
import base64
import os
from pathlib import Path

# Configuration
PROJECT_ID = os.environ.get("PROJECT_ID", "clinical-assistant-457902")
PROJECT_NUMBER = os.environ.get("PROJECT_NUMBER", "930035889332")
LOCATION = os.environ.get("LOCATION", "us")  # Document AI location
RAG_LOCATION = os.environ.get("RAG_LOCATION", "us-west4")  # RAG location
PROCESSOR_ID = os.environ.get("PROCESSOR_ID", "40e813cb62d57ea8")
CORPUS_ID = os.environ.get("CORPUS_ID", "2305843009213693952")

# Bucket names
RAW_BUCKET = f"{PROJECT_ID}-protocols-raw"
PROCESSED_BUCKET = f"{PROJECT_ID}-protocols-processed"


def get_access_token():
    """Get OAuth2 access token for REST API calls"""
    credentials, _ = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token


def extract_text_with_document_ai(bucket_name: str, blob_name: str) -> dict:
    """Extract text and metadata from PDF using Document AI"""
    
    print(f"📄 Processing: gs://{bucket_name}/{blob_name}")
    
    # Download PDF from GCS
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    pdf_content = blob.download_as_bytes()
    
    # Process with Document AI
    client = documentai.DocumentProcessorServiceClient(
        client_options={"api_endpoint": f"{LOCATION}-documentai.googleapis.com"}
    )
    
    processor_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{PROCESSOR_ID}"
    
    raw_document = documentai.RawDocument(
        content=pdf_content,
        mime_type="application/pdf"
    )
    
    request = documentai.ProcessRequest(
        name=processor_name,
        raw_document=raw_document
    )
    
    result = client.process_document(request=request)
    document = result.document
    
    # Extract text
    full_text = document.text
    
    # Extract confidence score
    confidence = 0.0
    if document.pages:
        confidences = [
            block.layout.confidence 
            for page in document.pages 
            for block in page.blocks 
            if block.layout.confidence
        ]
        if confidences:
            confidence = sum(confidences) / len(confidences)
    
    # Extract images from pages
    images = []
    for i, page in enumerate(document.pages):
        if page.image and page.image.content:
            images.append({
                "page": i + 1,
                "content": base64.b64encode(page.image.content).decode()
            })
    
    print(f"  ✅ Extracted {len(full_text)} chars, {len(images)} images, confidence: {confidence:.2%}")
    
    return {
        "text": full_text,
        "page_count": len(document.pages),
        "confidence": confidence,
        "images": images
    }


def save_processed_content(org_id: str, protocol_id: str, extracted: dict):
    """Save extracted text and images to processed bucket"""
    
    storage_client = storage.Client()
    bucket = storage_client.bucket(PROCESSED_BUCKET)
    
    # Save text
    text_blob = bucket.blob(f"{org_id}/{protocol_id}/extracted_text.txt")
    text_blob.upload_from_string(extracted["text"])
    text_uri = f"gs://{PROCESSED_BUCKET}/{org_id}/{protocol_id}/extracted_text.txt"
    print(f"  📝 Saved text to: {text_uri}")
    
    # Save images and collect their URIs
    image_info = []
    for img in extracted["images"]:
        img_path = f"{org_id}/{protocol_id}/images/page_{img['page']}.png"
        img_blob = bucket.blob(img_path)
        img_blob.upload_from_string(
            base64.b64decode(img["content"]),
            content_type="image/png"
        )
        
        # Store both GCS URI and public URL format
        gcs_uri = f"gs://{PROCESSED_BUCKET}/{img_path}"
        # Public URL (if bucket is public) or signed URL can be generated later
        image_info.append({
            "page": img["page"],
            "gcs_uri": gcs_uri,
            "path": img_path
        })
    
    if image_info:
        print(f"  🖼️  Saved {len(image_info)} images")
    
    # Save comprehensive metadata (links text to images)
    metadata = {
        "org_id": org_id,
        "protocol_id": protocol_id,
        "page_count": extracted["page_count"],
        "confidence": extracted["confidence"],
        "char_count": len(extracted["text"]),
        "text_uri": text_uri,
        "images": image_info,  # Array of {page, gcs_uri, path}
        "image_count": len(image_info)
    }
    meta_blob = bucket.blob(f"{org_id}/{protocol_id}/metadata.json")
    meta_blob.upload_from_string(json.dumps(metadata, indent=2))
    print(f"  � Saved metadata with {len(image_info)} image references")
    
    return text_uri, image_info, metadata


def index_to_rag_corpus(text_uri: str, display_name: str):
    """Index the extracted text into the RAG corpus"""
    
    corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{CORPUS_ID}"
    
    # Import file to RAG corpus
    url = f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1beta1/{corpus_name}/ragFiles:import"
    
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "importRagFilesConfig": {
            "gcsSource": {
                "uris": [text_uri]
            },
            "ragFileChunkingConfig": {
                "chunkSize": 1024,
                "chunkOverlap": 200
            }
        }
    }
    
    print(f"  🔄 Indexing to RAG corpus...")
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        result = response.json()
        operation_name = result.get("name", "")
        print(f"  ✅ RAG indexing started: {operation_name}")
        return True, operation_name
    else:
        print(f"  ❌ RAG indexing failed: {response.status_code}")
        print(f"     {response.text[:500]}")
        return False, response.text


def parse_gcs_path(gcs_uri: str) -> tuple:
    """Parse gs://bucket/path into (bucket, path)"""
    if gcs_uri.startswith("gs://"):
        parts = gcs_uri[5:].split("/", 1)
        return parts[0], parts[1] if len(parts) > 1 else ""
    return None, None


def extract_org_and_protocol(blob_name: str) -> tuple:
    """
    Extract org_id and protocol_id from blob path
    Expected format: {org_id}/{filename}.pdf or {org_id}/protocols/{filename}.pdf
    """
    parts = blob_name.split("/")
    
    if len(parts) >= 2:
        org_id = parts[0]
        # Use filename without extension as protocol_id
        filename = parts[-1]
        protocol_id = Path(filename).stem
        return org_id, protocol_id
    elif len(parts) == 1:
        # No org folder, use 'default' org
        filename = parts[0]
        protocol_id = Path(filename).stem
        return "default", protocol_id
    
    return None, None


@functions_framework.cloud_event
def process_pdf(cloud_event):
    """
    Cloud Function triggered by Cloud Storage upload
    Processes PDF and indexes to RAG corpus
    """
    
    data = cloud_event.data
    bucket_name = data["bucket"]
    blob_name = data["name"]
    
    print(f"\n{'='*60}")
    print(f"📥 New file uploaded: gs://{bucket_name}/{blob_name}")
    print('='*60)
    
    # Only process PDFs
    if not blob_name.lower().endswith(".pdf"):
        print(f"⏭️  Skipping non-PDF file: {blob_name}")
        return {"status": "skipped", "reason": "not a PDF"}
    
    # Extract org and protocol IDs
    org_id, protocol_id = extract_org_and_protocol(blob_name)
    if not org_id or not protocol_id:
        print(f"❌ Could not parse org/protocol from path: {blob_name}")
        return {"status": "error", "reason": "invalid path format"}
    
    print(f"📁 Organization: {org_id}")
    print(f"📄 Protocol: {protocol_id}")
    
    try:
        # Step 1: Extract text with Document AI
        extracted = extract_text_with_document_ai(bucket_name, blob_name)
        
        # Step 2: Save to processed bucket (text, images, metadata)
        text_uri, image_info, metadata = save_processed_content(org_id, protocol_id, extracted)
        
        # Step 3: Index to RAG corpus
        success, operation = index_to_rag_corpus(text_uri, protocol_id)
        
        result = {
            "status": "success" if success else "partial",
            "org_id": org_id,
            "protocol_id": protocol_id,
            "text_uri": text_uri,
            "images": image_info,
            "image_count": len(image_info),
            "char_count": len(extracted["text"]),
            "confidence": extracted["confidence"],
            "rag_indexed": success
        }
        
        print(f"\n✅ Processing complete!")
        print(json.dumps(result, indent=2))
        
        return result
        
    except Exception as e:
        print(f"\n❌ Error processing PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


# For local testing
def test_local(pdf_path: str, org_id: str = "test-org"):
    """Test the pipeline locally without Cloud Functions"""
    
    print(f"\n{'='*60}")
    print(f"🧪 Local Test Mode")
    print('='*60)
    
    # Upload to raw bucket first
    storage_client = storage.Client()
    bucket = storage_client.bucket(RAW_BUCKET)
    
    filename = Path(pdf_path).name
    protocol_id = Path(pdf_path).stem
    blob_name = f"{org_id}/{filename}"
    
    print(f"📤 Uploading to: gs://{RAW_BUCKET}/{blob_name}")
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(pdf_path)
    
    # Now process it
    extracted = extract_text_with_document_ai(RAW_BUCKET, blob_name)
    text_uri, image_info, metadata = save_processed_content(org_id, protocol_id, extracted)
    success, operation = index_to_rag_corpus(text_uri, protocol_id)
    
    return {
        "status": "success" if success else "partial",
        "org_id": org_id,
        "protocol_id": protocol_id,
        "text_uri": text_uri,
        "images": image_info,
        "rag_indexed": success
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = test_local(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "test-org")
        print(json.dumps(result, indent=2))
    else:
        print("Usage: python main.py <pdf_path> [org_id]")
