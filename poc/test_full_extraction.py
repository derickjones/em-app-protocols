#!/usr/bin/env python3
"""
Enhanced Document AI test - Extract text AND images
Saves to proper directory structure
"""

import os
import json
import base64
import subprocess
from pathlib import Path
import requests
from PIL import Image
import io

PROJECT_ID = "clinical-assistant-457902"
LOCATION = "us"
PROCESSOR_ID = "40e813cb62d57ea8"

def get_access_token():
    """Get access token from gcloud"""
    result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True
    )
    return result.stdout.strip()

def save_page_images(pages, pdf_name, output_dir):
    """Extract and save page images"""
    images_dir = output_dir / "extracted_images" / pdf_name
    images_dir.mkdir(parents=True, exist_ok=True)
    
    image_count = 0
    for page_num, page in enumerate(pages, start=1):
        # Get page image if available
        if "image" in page and "content" in page["image"]:
            try:
                # Decode base64 image
                image_data = base64.b64decode(page["image"]["content"])
                
                # Save as PNG
                image_path = images_dir / f"page_{page_num}.png"
                with open(image_path, "wb") as f:
                    f.write(image_data)
                
                print(f"    📸 Saved page {page_num} image: {image_path.name}")
                image_count += 1
            except Exception as e:
                print(f"    ⚠️  Could not save page {page_num} image: {e}")
    
    return image_count

def process_pdf(pdf_path):
    """Process PDF using Document AI REST API with image extraction"""
    print(f"\n📄 Processing: {pdf_path}")
    
    # Read PDF
    with open(pdf_path, "rb") as f:
        pdf_content = f.read()
    
    # Encode to base64
    encoded_pdf = base64.b64encode(pdf_content).decode('utf-8')
    
    # Prepare request with image extraction enabled
    url = f"https://us-documentai.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/processors/{PROCESSOR_ID}:process"
    
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }
    
    # Enable all features including image extraction
    payload = {
        "rawDocument": {
            "content": encoded_pdf,
            "mimeType": "application/pdf"
        },
        "processOptions": {
            "ocrConfig": {
                "enableImageQualityScores": True,
                "enableNativePdfParsing": True
            }
        }
    }
    
    # Make request
    print("  ⏳ Calling Document AI API (with image extraction)...")
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        print(f"  ❌ Error: {response.status_code}")
        print(response.text)
        return None
    
    # Parse response
    result = response.json()
    document = result.get("document", {})
    
    # Extract info
    text = document.get("text", "")
    pages = document.get("pages", [])
    
    num_pages = len(pages)
    text_length = len(text)
    
    # Calculate confidence
    confidences = []
    for page in pages:
        layout = page.get("layout", {})
        if "confidence" in layout:
            confidences.append(layout["confidence"])
    
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    
    print(f"  ✅ Pages: {num_pages}")
    print(f"  ✅ Characters: {text_length:,}")
    print(f"  ✅ Confidence: {avg_confidence:.1%}")
    
    # Create output directories
    pdf_name = Path(pdf_path).stem
    output_dir = Path("output")
    text_dir = output_dir / "extracted_text"
    text_dir.mkdir(parents=True, exist_ok=True)
    
    # Save text to proper directory
    text_file = text_dir / f"{pdf_name}.txt"
    with open(text_file, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  💾 Text saved: {text_file}")
    
    # Extract and save images
    print(f"  🖼️  Extracting images...")
    image_count = save_page_images(pages, pdf_name, output_dir)
    print(f"  ✅ Saved {image_count} page images")
    
    # Save metadata to proper directory
    metadata = {
        "pdf_name": pdf_name,
        "pages": num_pages,
        "characters": text_length,
        "images_extracted": image_count,
        "confidence": avg_confidence,
        "quality_score": int(avg_confidence * 10),
        "text_file": str(text_file),
        "images_dir": f"output/extracted_images/{pdf_name}"
    }
    
    metadata_file = text_dir / f"{pdf_name}_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  💾 Metadata saved: {metadata_file}")
    
    return metadata

def main():
    print("="*60)
    print("  Document AI POC - Full Extraction (Text + Images)")
    print("  Project: clinical-assistant-457902")
    print("  Processor: 40e813cb62d57ea8")
    print("="*60)
    
    # Find PDFs
    pdf_dir = Path("sample_pdfs")
    pdf_files = list(pdf_dir.glob("*.pdf"))
    
    if not pdf_files:
        print("\n❌ No PDFs found in sample_pdfs/")
        return
    
    print(f"\n📋 Found {len(pdf_files)} PDFs to process\n")
    
    # Process each PDF
    results = []
    for pdf_path in pdf_files:
        try:
            metadata = process_pdf(str(pdf_path))
            if metadata:
                results.append(metadata)
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            continue
    
    # Summary
    print("\n" + "="*60)
    print("  SUMMARY")
    print("="*60)
    
    if not results:
        print("❌ No PDFs were successfully processed")
        return
    
    print(f"Processed: {len(results)}/{len(pdf_files)} PDFs")
    
    avg_quality = sum(r['quality_score'] for r in results) / len(results)
    avg_confidence = sum(r['confidence'] for r in results) / len(results)
    total_pages = sum(r['pages'] for r in results)
    total_chars = sum(r['characters'] for r in results)
    total_images = sum(r['images_extracted'] for r in results)
    
    print(f"Total pages: {total_pages}")
    print(f"Total characters: {total_chars:,}")
    print(f"Total images: {total_images}")
    print(f"Average confidence: {avg_confidence:.1%}")
    print(f"Average quality score: {avg_quality:.1f}/10")
    
    print("\n📂 Output Structure:")
    print("  output/")
    print("    ├── extracted_text/")
    for r in results:
        print(f"    │   ├── {r['pdf_name']}.txt")
        print(f"    │   └── {r['pdf_name']}_metadata.json")
    print("    └── extracted_images/")
    for r in results:
        print(f"        └── {r['pdf_name']}/")
        print(f"            └── page_X.png")
    
    print("\n" + "="*60)
    if avg_quality >= 8:
        print("  ✅ SUCCESS - Ready for Day 2!")
        print("  Quality is excellent for RAG indexing")
    elif avg_quality >= 6:
        print("  ⚠️  FAIR - May proceed with caution")
        print("  Quality is acceptable but not ideal")
    else:
        print("  ❌ POOR - Need different approach")
        print("  Quality is too low for reliable RAG")
    print("="*60)

if __name__ == "__main__":
    main()
