#!/usr/bin/env python3
"""
Day 2 - Task 1: Create Vertex AI RAG Corpus
Goal: Set up a RAG corpus for storing EM protocol content

Success Criteria:
- RAG corpus created
- Corpus ID saved for indexing
- Ready to accept protocol documents
"""

import subprocess
import json
import requests
from pathlib import Path

PROJECT_ID = "clinical-assistant-457902"
LOCATION = "us-central1"
CORPUS_DISPLAY_NAME = "em-protocols-corpus"

def get_access_token():
    """Get access token from gcloud"""
    result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True
    )
    return result.stdout.strip()

def create_rag_corpus():
    """Create a Vertex AI RAG corpus"""
    print("="*60)
    print("  Task 1: Create Vertex AI RAG Corpus")
    print("="*60)
    
    # Check if corpus already exists
    print("\n🔍 Checking for existing corpora...")
    
    list_url = f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/projects/{PROJECT_ID}/locations/{LOCATION}/ragCorpora"
    
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(list_url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        corpora = data.get("ragCorpora", [])
        
        # Check if our corpus already exists
        for corpus in corpora:
            if CORPUS_DISPLAY_NAME in corpus.get("displayName", ""):
                corpus_name = corpus["name"]
                corpus_id = corpus_name.split("/")[-1]
                print(f"✅ Corpus already exists!")
                print(f"   Name: {corpus.get('displayName')}")
                print(f"   ID: {corpus_id}")
                save_config(corpus_id, corpus_name)
                return corpus_id
    
    # Create new corpus
    print(f"\n📦 Creating new RAG corpus: {CORPUS_DISPLAY_NAME}")
    
    create_url = f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/projects/{PROJECT_ID}/locations/{LOCATION}/ragCorpora"
    
    payload = {
        "displayName": CORPUS_DISPLAY_NAME,
        "description": "Emergency Medicine protocols for clinical decision support",
        "ragEmbeddingModelConfig": {
            "vertexPredictionEndpoint": {
                "publisherModel": f"projects/{PROJECT_ID}/locations/{LOCATION}/publishers/google/models/text-embedding-004"
            }
        }
    }
    
    print("  ⏳ Calling Vertex AI API...")
    response = requests.post(create_url, headers=headers, json=payload)
    
    if response.status_code == 200:
        result = response.json()
        
        # The response is a long-running operation
        if "name" in result and "operations" in result["name"]:
            print("  ⏳ Corpus creation in progress...")
            operation_name = result["name"]
            
            # Poll for completion
            import time
            for i in range(30):  # Wait up to 30 seconds
                op_response = requests.get(
                    f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/{operation_name}",
                    headers=headers
                )
                op_data = op_response.json()
                
                if op_data.get("done"):
                    if "response" in op_data:
                        corpus_data = op_data["response"]
                        corpus_name = corpus_data["name"]
                        corpus_id = corpus_name.split("/")[-1]
                        print(f"\n✅ Corpus created successfully!")
                        print(f"   Name: {corpus_data.get('displayName')}")
                        print(f"   ID: {corpus_id}")
                        save_config(corpus_id, corpus_name)
                        return corpus_id
                    elif "error" in op_data:
                        print(f"\n❌ Error: {op_data['error']}")
                        return None
                
                print(f"  ⏳ Waiting... ({i+1}/30)")
                time.sleep(1)
            
            print("  ⚠️ Operation timed out, checking status...")
        else:
            # Direct response (corpus created immediately)
            corpus_name = result.get("name", "")
            corpus_id = corpus_name.split("/")[-1] if corpus_name else None
            
            if corpus_id:
                print(f"\n✅ Corpus created successfully!")
                print(f"   ID: {corpus_id}")
                save_config(corpus_id, corpus_name)
                return corpus_id
    else:
        print(f"\n❌ Error creating corpus: {response.status_code}")
        print(response.text)
        return None

def save_config(corpus_id, corpus_name):
    """Save corpus configuration for later use"""
    config = {
        "project_id": PROJECT_ID,
        "location": LOCATION,
        "corpus_id": corpus_id,
        "corpus_name": corpus_name,
        "corpus_display_name": CORPUS_DISPLAY_NAME
    }
    
    config_path = Path("rag_config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"\n💾 Config saved to: {config_path}")

def main():
    corpus_id = create_rag_corpus()
    
    if corpus_id:
        print("\n" + "="*60)
        print("  ✅ Task 1 Complete!")
        print("="*60)
        print(f"\nRAG Corpus ID: {corpus_id}")
        print("\nNext steps:")
        print("  1. Run: python test_rag_index.py   (Index protocols)")
        print("  2. Run: python test_rag_query.py   (Test queries)")
    else:
        print("\n" + "="*60)
        print("  ❌ Task 1 Failed")
        print("="*60)
        print("\nTroubleshooting:")
        print("  1. Check authentication: gcloud auth application-default login")
        print("  2. Check project permissions in GCP Console")
        print("  3. Verify Vertex AI API is enabled")

if __name__ == "__main__":
    main()
