#!/usr/bin/env python3
"""
Day 2 - Task 2: Index Protocol Content into RAG Corpus
Goal: Upload and index extracted protocol text for RAG queries

Success Criteria:
- Both protocols indexed successfully
- Content searchable via RAG queries
- Metadata (protocol name, pages) preserved
"""

import subprocess
import json
import requests
import base64
from pathlib import Path
import time

# Load config
with open("rag_config.json") as f:
    config = json.load(f)

PROJECT_ID = config["project_id"]
PROJECT_NUMBER = config["project_number"]
LOCATION = config["location"]
CORPUS_ID = config["corpus_id"]
CORPUS_NAME = config["corpus_name"]

# Document AI config
DOC_AI_LOCATION = "us"
DOC_AI_PROCESSOR_ID = "40e813cb62d57ea8"

def get_access_token():
    """Get access token from gcloud"""
    result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True
    )
    return result.stdout.strip()

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using Document AI"""
    print(f"\n📄 Extracting text from: {pdf_path}")
    
    with open(pdf_path, "rb") as f:
        pdf_content = f.read()
    
    encoded_pdf = base64.b64encode(pdf_content).decode('utf-8')
    
    url = f"https://{DOC_AI_LOCATION}-documentai.googleapis.com/v1/projects/{PROJECT_ID}/locations/{DOC_AI_LOCATION}/processors/{DOC_AI_PROCESSOR_ID}:process"
    
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "rawDocument": {
            "content": encoded_pdf,
            "mimeType": "application/pdf"
        }
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        print(f"  ❌ Error: {response.status_code}")
        return None
    
    result = response.json()
    document = result.get("document", {})
    text = document.get("text", "")
    pages = document.get("pages", [])
    
    print(f"  ✅ Extracted {len(text):,} characters from {len(pages)} pages")
    return text

def upload_to_rag_corpus(pdf_name, text_content):
    """Upload text content to RAG corpus as a RAG file"""
    print(f"\n📤 Uploading to RAG corpus: {pdf_name}")
    
    # First, we need to upload the file to GCS or use inline content
    # RAG API accepts files from GCS, so let's use the import API with inline content
    
    url = f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/{CORPUS_NAME}/ragFiles:import"
    
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }
    
    # Create a unique file display name
    file_display_name = pdf_name.replace("_", " ").replace(".pdf", "")
    
    # Use inline upload via GCS
    # First upload to GCS bucket
    bucket_name = f"{PROJECT_ID}-protocols-raw"
    gcs_path = f"gs://{bucket_name}/rag-input/{pdf_name}.txt"
    
    print(f"  ⏳ Uploading text to GCS: {gcs_path}")
    
    # Upload to GCS using gsutil
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(text_content)
        temp_path = f.name
    
    gsutil_result = subprocess.run(
        ["gsutil", "cp", temp_path, gcs_path],
        capture_output=True,
        text=True
    )
    
    if gsutil_result.returncode != 0:
        print(f"  ❌ GCS upload failed: {gsutil_result.stderr}")
        return None
    
    print(f"  ✅ Uploaded to GCS")
    
    # Now import into RAG corpus
    print(f"  ⏳ Importing into RAG corpus...")
    
    payload = {
        "importRagFilesConfig": {
            "gcsSource": {
                "uris": [gcs_path]
            },
            "ragFileChunkingConfig": {
                "chunkSize": 1024,
                "chunkOverlap": 200
            }
        }
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        print(f"  ❌ Import failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return None
    
    result = response.json()
    
    # This returns a long-running operation
    if "name" in result:
        operation_name = result["name"]
        print(f"  ⏳ Import operation started: {operation_name.split('/')[-1]}")
        
        # Poll for completion
        for i in range(30):
            op_url = f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/{operation_name}"
            op_response = requests.get(op_url, headers=headers)
            op_data = op_response.json()
            
            if op_data.get("done"):
                if "error" in op_data:
                    print(f"  ❌ Import error: {op_data['error']}")
                    return None
                print(f"  ✅ Import complete!")
                return op_data.get("response", {})
            
            time.sleep(2)
        
        print(f"  ⚠️ Import still running (may complete in background)")
        return {"status": "pending", "operation": operation_name}
    
    return result

def list_rag_files():
    """List all files in the RAG corpus"""
    print("\n📋 Files in RAG corpus:")
    
    url = f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/{CORPUS_NAME}/ragFiles"
    
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        files = data.get("ragFiles", [])
        
        if not files:
            print("  (no files yet)")
            return []
        
        for f in files:
            name = f.get("displayName", f.get("name", "unknown"))
            size = f.get("sizeBytes", 0)
            print(f"  • {name} ({int(size):,} bytes)")
        
        return files
    else:
        print(f"  ❌ Error listing files: {response.status_code}")
        return []

def main():
    print("="*60)
    print("  Task 2: Index Protocol Content into RAG Corpus")
    print("="*60)
    print(f"\nCorpus: {CORPUS_NAME}")
    print(f"Location: {LOCATION}")
    
    # Find PDFs
    pdf_dir = Path("sample_pdfs")
    pdf_files = list(pdf_dir.glob("*.pdf"))
    
    if not pdf_files:
        print("\n❌ No PDFs found in sample_pdfs/")
        return
    
    print(f"\n📋 Found {len(pdf_files)} PDFs to index")
    
    # Process each PDF
    results = []
    for pdf_path in pdf_files:
        pdf_name = pdf_path.stem
        
        # Step 1: Extract text
        text = extract_text_from_pdf(str(pdf_path))
        if not text:
            print(f"  ❌ Failed to extract text from {pdf_name}")
            continue
        
        # Save extracted text locally
        output_dir = Path("output/extracted_text")
        output_dir.mkdir(parents=True, exist_ok=True)
        text_file = output_dir / f"{pdf_name}.txt"
        with open(text_file, "w") as f:
            f.write(text)
        print(f"  💾 Saved to: {text_file}")
        
        # Step 2: Upload to RAG corpus
        result = upload_to_rag_corpus(pdf_name, text)
        results.append({
            "pdf_name": pdf_name,
            "text_length": len(text),
            "upload_result": result
        })
    
    # Summary
    print("\n" + "="*60)
    print("  SUMMARY")
    print("="*60)
    
    successful = sum(1 for r in results if r.get("upload_result"))
    print(f"\nProcessed: {len(results)} PDFs")
    print(f"Indexed: {successful}/{len(results)}")
    
    # List files in corpus
    list_rag_files()
    
    if successful > 0:
        print("\n" + "="*60)
        print("  ✅ Task 2 Complete!")
        print("="*60)
        print("\nNext steps:")
        print("  Run: python test_rag_query.py   (Test RAG queries)")
    else:
        print("\n" + "="*60)
        print("  ⚠️ Task 2 - Check Results")
        print("="*60)

if __name__ == "__main__":
    main()
