#!/usr/bin/env python3
"""
Simple Document AI setup and test script
Goal: Extract text and images from 2 protocol PDFs

Usage: python test_doc_ai_simple.py
"""

import os
import json
from pathlib import Path
from google.cloud import documentai_v1 as documentai
from google.api_core.client_options import ClientOptions
import time

# Configuration
PROJECT_ID = "clinical-assistant-457902"
LOCATION = "us"
PROCESSOR_DISPLAY_NAME = "em-protocol-processor"

def create_processor():
    """Create a Document AI processor"""
    print("🔧 Creating Document AI processor...")
    
    client_options = ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")
    client = documentai.DocumentProcessorServiceClient(client_options=client_options)
    
    parent = f"projects/{PROJECT_ID}/locations/{LOCATION}"
    
    try:
        # Create processor
        processor = client.create_processor(
            parent=parent,
            processor=documentai.Processor(
                display_name=PROCESSOR_DISPLAY_NAME,
                type_="OCR_PROCESSOR"
            )
        )
        processor_id = processor.name.split("/")[-1]
        print(f"✅ Processor created: {processor_id}")
        return processor_id
    except Exception as e:
        if "already exists" in str(e):
            print("⚠️  Processor already exists, listing processors...")
            # List existing processors
            processors = client.list_processors(parent=parent)
            for proc in processors:
                if PROCESSOR_DISPLAY_NAME in proc.display_name:
                    processor_id = proc.name.split("/")[-1]
                    print(f"✅ Using existing processor: {processor_id}")
                    return processor_id
        raise e

def process_pdf(processor_id, pdf_path):
    """Process a PDF with Document AI"""
    print(f"\n📄 Processing: {pdf_path}")
    start_time = time.time()
    
    client_options = ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")
    client = documentai.DocumentProcessorServiceClient(client_options=client_options)
    
    name = f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{processor_id}"
    
    # Read PDF
    with open(pdf_path, "rb") as f:
        pdf_content = f.read()
    
    # Process
    raw_document = documentai.RawDocument(content=pdf_content, mime_type="application/pdf")
    request = documentai.ProcessRequest(name=name, raw_document=raw_document)
    
    result = client.process_document(request=request)
    document = result.document
    
    processing_time = time.time() - start_time
    
    # Extract info
    num_pages = len(document.pages)
    text_length = len(document.text)
    
    # Get confidence
    confidences = [page.layout.confidence for page in document.pages if page.layout]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    
    print(f"  ✅ Pages: {num_pages}")
    print(f"  ✅ Characters: {text_length:,}")
    print(f"  ✅ Confidence: {avg_confidence:.1%}")
    print(f"  ✅ Time: {processing_time:.2f}s")
    
    # Save results
    pdf_name = Path(pdf_path).stem
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # Save text
    text_file = output_dir / f"{pdf_name}_text.txt"
    with open(text_file, "w") as f:
        f.write(document.text)
    print(f"  💾 Text saved: {text_file}")
    
    # Save metadata
    metadata = {
        "pdf_name": pdf_name,
        "pages": num_pages,
        "characters": text_length,
        "confidence": avg_confidence,
        "processing_time": processing_time,
        "quality_score": int(avg_confidence * 10)
    }
    
    metadata_file = output_dir / f"{pdf_name}_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  💾 Metadata saved: {metadata_file}")
    
    return metadata

def main():
    print("="*60)
    print("  Document AI POC - Day 1 Test")
    print("  Project: clinical-assistant-457902")
    print("="*60)
    
    # Step 1: Create processor
    processor_id = create_processor()
    
    # Update .env file
    env_file = Path(".env")
    env_content = env_file.read_text()
    if "DOCUMENT_AI_PROCESSOR_ID=" in env_content and not env_content.split("DOCUMENT_AI_PROCESSOR_ID=")[1].split("\n")[0].strip():
        env_content = env_content.replace(
            "DOCUMENT_AI_PROCESSOR_ID=",
            f"DOCUMENT_AI_PROCESSOR_ID={processor_id}"
        )
        env_file.write_text(env_content)
        print(f"✅ Updated .env with processor ID")
    
    # Step 2: Process PDFs
    pdf_dir = Path("sample_pdfs")
    pdf_files = list(pdf_dir.glob("*.pdf"))
    
    if not pdf_files:
        print("\n❌ No PDFs found in sample_pdfs/")
        return
    
    print(f"\n📋 Found {len(pdf_files)} PDFs to process\n")
    
    results = []
    for pdf_path in pdf_files:
        try:
            metadata = process_pdf(processor_id, str(pdf_path))
            results.append(metadata)
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
            continue
    
    # Summary
    print("\n" + "="*60)
    print("  Summary")
    print("="*60)
    print(f"Processed: {len(results)}/{len(pdf_files)} PDFs")
    if results:
        avg_quality = sum(r['quality_score'] for r in results) / len(results)
        avg_confidence = sum(r['confidence'] for r in results) / len(results)
        total_pages = sum(r['pages'] for r in results)
        
        print(f"Total pages: {total_pages}")
        print(f"Average confidence: {avg_confidence:.1%}")
        print(f"Average quality score: {avg_quality:.1f}/10")
        print(f"\n{'✅ SUCCESS' if avg_quality >= 8 else '⚠️  NEEDS IMPROVEMENT'}")
        print(f"Ready for Day 2: {'YES' if avg_quality >= 8 else 'NO - Review quality'}")

if __name__ == "__main__":
    main()
