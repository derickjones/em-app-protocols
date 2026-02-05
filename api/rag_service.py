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
        # Build context string - limit to top 3 for speed
        context_text = "\n---\n".join([
            f"[{i+1}] {c['text'][:1500]}"
            for i, c in enumerate(contexts[:3])
        ])
        
        # Gemini endpoint (us-central1 for low latency)
        url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{self.project_id}/locations/us-central1/publishers/google/models/gemini-2.0-flash:generateContent"
        
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json"
        }
        
        prompt = f"""Emergency medicine assistant for ED physicians. Use markdown formatting.

MARKDOWN FORMAT RULES:
- Use "- " (dash space) at start of line for bullet points
- Use "**text**" for bold headers and drug names  
- Use blank lines between sections
- Add [1] citations at end of sentences

STRUCTURE:
1. Bold header + 1-2 sentence intro paragraph
2. Subheaders with bullet lists under them
3. Keep bullets short

EXAMPLE (copy this exact markdown style):

**Cardiac Arrest Management**

Start CPR immediately at 100-120/min with 2+ inch depth. Secure IV/IO access. [1]

**For VF/pVT:**

- Defibrillate 200J biphasic
- Resume CPR 2 min, reassess rhythm
- **Epinephrine** 1mg IV q3-5min after 2nd shock
- **Amiodarone** 300mg IV if refractory [1]

**For Asystole/PEA:**

- Start CPR and **epinephrine** 1mg IV immediately
- Identify reversible causes (Hs and Ts) [1]

CONTEXT:
{context_text}

Q: {query}
A:"""

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 400
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
