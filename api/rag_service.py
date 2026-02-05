"""
RAG Service
Handles RAG queries and Gemini answer generation
"""

import os
import json
import requests
import google.auth
import google.auth.transport.requests
from typing import Dict, List, Optional
from google.cloud import storage

# Configuration
PROJECT_ID = os.environ.get("PROJECT_ID", "clinical-assistant-457902")
PROJECT_NUMBER = os.environ.get("PROJECT_NUMBER", "930035889332")
RAG_LOCATION = os.environ.get("RAG_LOCATION", "us-west4")
CORPUS_ID = os.environ.get("CORPUS_ID", "2305843009213693952")
PROCESSED_BUCKET = f"{PROJECT_ID}-protocols-processed"


class RAGService:
    """Service for RAG queries and answer generation"""
    
    def __init__(self):
        self.project_id = PROJECT_ID
        self.project_number = PROJECT_NUMBER
        self.location = RAG_LOCATION
        self.corpus_id = CORPUS_ID
        self.corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{CORPUS_ID}"
        self.storage_client = storage.Client()
        self._metadata_cache = {}
    
    def _get_access_token(self) -> str:
        """Get OAuth2 access token"""
        credentials, _ = google.auth.default()
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        return credentials.token
    
    def _retrieve_contexts(self, query: str, top_k: int = 5) -> List[Dict]:
        """Retrieve relevant contexts from RAG corpus"""
        url = f"https://{self.location}-aiplatform.googleapis.com/v1beta1/projects/{self.project_number}/locations/{self.location}:retrieveContexts"
        
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": {"text": query},
            "vertex_rag_store": {
                "rag_corpora": [self.corpus_name]
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            raise Exception(f"RAG retrieval failed: {response.status_code} - {response.text}")
        
        result = response.json()
        contexts = []
        
        if "contexts" in result:
            for ctx in result["contexts"].get("contexts", []):
                contexts.append({
                    "text": ctx.get("text", ""),
                    "source": ctx.get("sourceUri", "unknown"),
                    "score": ctx.get("score", 0)
                })
        
        return contexts
    
    def _generate_answer(self, query: str, contexts: List[Dict]) -> str:
        """Generate answer using Gemini (fast - no grounding overhead)"""
        # Build context string with source labels for citation
        context_text = "\n\n---\n".join([
            f"[{i+1}] {c['text']}"
            for i, c in enumerate(contexts)
        ])
        
        # Gemini endpoint (us-central1 for low latency)
        url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{self.project_id}/locations/us-central1/publishers/google/models/gemini-2.0-flash:generateContent"
        
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json"
        }
        
        prompt = f"""You are an emergency medicine clinical decision support assistant for ED physicians.

FORMATTING RULES:
- Use markdown bullet points "- " for lists
- Use numbered lists "1. " for sequential steps
- Use **bold** for headers and critical warnings
- Keep it scannable for busy ED physicians

STRUCTURE:
**Immediate Actions**
- Critical action [1]

**Key Steps**
1. Step one [1]
2. Step two [2]

**Medications** (if applicable)
- **Drug**: dose, route, frequency [1]

Add citation numbers [1], [2] etc. after statements referencing that source.

PROTOCOL CONTEXT:
{context_text}

QUESTION: {query}

ANSWER:"""

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 800
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            raise Exception(f"Gemini generation failed: {response.status_code} - {response.text}")
        
        result = response.json()
        return result["candidates"][0]["content"]["parts"][0]["text"]
    
    def _get_protocol_metadata(self, source_uri: str) -> Optional[Dict]:
        """Get metadata for a protocol from its source URI"""
        # Parse source URI to get org_id and protocol_id
        # Format: gs://bucket/org_id/protocol_id/extracted_text.txt
        try:
            if source_uri.startswith("gs://"):
                parts = source_uri.split("/")
                if len(parts) >= 5:
                    org_id = parts[3]
                    protocol_id = parts[4]
                    
                    cache_key = f"{org_id}/{protocol_id}"
                    if cache_key in self._metadata_cache:
                        return self._metadata_cache[cache_key]
                    
                    bucket = self.storage_client.bucket(PROCESSED_BUCKET)
                    blob = bucket.blob(f"{org_id}/{protocol_id}/metadata.json")
                    
                    if blob.exists():
                        content = blob.download_as_string()
                        metadata = json.loads(content)
                        self._metadata_cache[cache_key] = metadata
                        return metadata
        except Exception as e:
            print(f"Error getting metadata for {source_uri}: {e}")
        
        return None
    
    def _get_images_from_contexts(self, contexts: List[Dict]) -> List[Dict]:
        """Extract images from context sources"""
        seen_images = set()
        images = []
        
        for ctx in contexts:
            metadata = self._get_protocol_metadata(ctx["source"])
            
            if metadata:
                for img in metadata.get("images", []):
                    img_key = img.get("gcs_uri", "")
                    if img_key and img_key not in seen_images:
                        seen_images.add(img_key)
                        
                        # Convert to public URL
                        url = img_key.replace(
                            "gs://",
                            "https://storage.googleapis.com/"
                        )
                        
                        images.append({
                            "page": img.get("page", 0),
                            "url": url,
                            "source": metadata.get("protocol_id", "unknown")
                        })
        
        # Sort by source and page
        images.sort(key=lambda x: (x["source"], x["page"]))
        
        return images
    
    def query(self, query: str, include_images: bool = True) -> Dict:
        """
        Execute a full RAG query (fast two-step approach)
        
        Returns:
            dict with answer, images, citations
        """
        # Step 1: Retrieve contexts from RAG corpus
        contexts = self._retrieve_contexts(query)
        
        if not contexts:
            return {
                "answer": "No relevant protocols found for this query.",
                "images": [],
                "citations": []
            }
        
        # Step 2: Generate answer with Gemini (fast, no grounding overhead)
        answer = self._generate_answer(query, contexts)
        
        # Step 3: Get images from contexts
        images = []
        if include_images:
            images = self._get_images_from_contexts(contexts)
        
        # Step 4: Build citations
        citations = [
            {
                "source": ctx["source"],
                "score": ctx["score"]
            }
            for ctx in contexts
        ]
        
        return {
            "answer": answer,
            "images": images,
            "citations": citations
        }
