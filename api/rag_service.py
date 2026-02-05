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
    
    def _generate_with_rag_grounding(self, query: str) -> Dict:
        """Generate answer using Gemini with RAG grounding - handles retrieval and citations automatically"""
        
        # Use v1beta1 for RAG grounding features
        url = f"https://{self.location}-aiplatform.googleapis.com/v1beta1/projects/{self.project_id}/locations/{self.location}/publishers/google/models/gemini-2.0-flash:generateContent"
        
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json"
        }
        
        system_prompt = """You are an emergency medicine clinical decision support assistant for ED physicians.

FORMATTING RULES:
1. Use proper markdown bullet points with "- " (dash space) for ALL lists
2. Use markdown numbered lists "1. " for sequential steps  
3. Indent sub-items with 2 spaces before the dash
4. Use **bold** for section headers and critical warnings
5. Use blank lines between sections for readability
6. Keep it scannable - busy ED physicians need to read this at a glance

STRUCTURE:
- **Immediate Actions**: What to do right now
- **Key Steps**: Numbered sequence if procedural
- **Medications**: Drug name, dose, route, frequency
- **Warnings**: Critical safety considerations in bold

Be concise. Lead with what matters most."""

        payload = {
            "contents": [{"role": "user", "parts": [{"text": query}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1000
            },
            "tools": [{
                "retrieval": {
                    "vertexRagStore": {
                        "ragCorpora": [self.corpus_name],
                        "similarityTopK": 5
                    }
                }
            }]
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            raise Exception(f"Gemini RAG generation failed: {response.status_code} - {response.text}")
        
        result = response.json()
        
        # Extract answer
        answer = result["candidates"][0]["content"]["parts"][0]["text"]
        
        # Extract grounding metadata for citations
        grounding_metadata = result["candidates"][0].get("groundingMetadata", {})
        grounding_chunks = grounding_metadata.get("groundingChunks", [])
        grounding_supports = grounding_metadata.get("groundingSupports", [])
        
        # Build citations from grounding metadata
        citations = []
        seen_sources = set()
        
        for chunk in grounding_chunks:
            if "retrievedContext" in chunk:
                source_uri = chunk["retrievedContext"].get("uri", "")
                if source_uri and source_uri not in seen_sources:
                    seen_sources.add(source_uri)
                    citations.append({
                        "source": source_uri,
                        "title": chunk["retrievedContext"].get("title", ""),
                        "score": 1.0  # Grounding doesn't return scores directly
                    })
        
        # Get contexts for image extraction
        contexts = [{"source": c["source"]} for c in citations]
        
        return {
            "answer": answer,
            "contexts": contexts,
            "citations": citations,
            "grounding_supports": grounding_supports
        }
    
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
        Execute a full RAG query using Gemini with RAG grounding
        
        Returns:
            dict with answer, images, citations
        """
        # Step 1: Retrieve contexts first - needed for images and proper citation URIs
        contexts = self._retrieve_contexts(query)
        
        if not contexts:
            return {
                "answer": "No relevant protocols found for this query.",
                "images": [],
                "citations": []
            }
        
        # Step 2: Use Gemini with RAG grounding for the answer (handles inline citations automatically)
        result = self._generate_with_rag_grounding(query)
        answer = result["answer"]
        
        if not answer or answer.strip() == "":
            return {
                "answer": "No relevant protocols found for this query.",
                "images": [],
                "citations": []
            }
        
        # Step 3: Get images from the retrieved contexts
        images = []
        if include_images:
            images = self._get_images_from_contexts(contexts)
        
        # Step 4: Build citations from retrieved contexts (has proper gs:// URIs)
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
