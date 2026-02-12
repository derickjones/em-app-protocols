"""
RAG Service
Handles RAG queries and Gemini answer generation
Supports multi-source queries (local protocols + WikEM + PMC literature)
"""

import os
import json
import requests
import google.auth
import google.auth.transport.requests
from typing import Dict, List, Optional
from google.cloud import storage
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
PROJECT_ID = os.environ.get("PROJECT_ID", "clinical-assistant-457902")
PROJECT_NUMBER = os.environ.get("PROJECT_NUMBER", "930035889332")
RAG_LOCATION = os.environ.get("RAG_LOCATION", "us-west4")
CORPUS_ID = os.environ.get("CORPUS_ID", "2305843009213693952")
WIKEM_CORPUS_ID = os.environ.get("WIKEM_CORPUS_ID", "6917529027641081856")
PMC_CORPUS_ID = os.environ.get("PMC_CORPUS_ID", "")
PROCESSED_BUCKET = f"{PROJECT_ID}-protocols-processed"
WIKEM_BUCKET = f"{PROJECT_ID}-wikem"
PMC_BUCKET = f"{PROJECT_ID}-pmc"


class RAGService:
    """Service for RAG queries and answer generation"""
    
    def __init__(self):
        self.project_id = PROJECT_ID
        self.project_number = PROJECT_NUMBER
        self.location = RAG_LOCATION
        self.corpus_id = CORPUS_ID
        self.wikem_corpus_id = WIKEM_CORPUS_ID
        self.pmc_corpus_id = PMC_CORPUS_ID
        self.corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{CORPUS_ID}"
        self.wikem_corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{WIKEM_CORPUS_ID}"
        self.pmc_corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{PMC_CORPUS_ID}" if PMC_CORPUS_ID else None
        self.storage_client = storage.Client()
        self._metadata_cache = {}
    
    def _get_access_token(self) -> str:
        """Get OAuth2 access token"""
        credentials, _ = google.auth.default()
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        return credentials.token
    
    def _retrieve_contexts(self, query: str, corpus_name: str = None, top_k: int = 5) -> List[Dict]:
        """Retrieve relevant contexts from a RAG corpus"""
        if corpus_name is None:
            corpus_name = self.corpus_name
            
        url = f"https://{self.location}-aiplatform.googleapis.com/v1beta1/projects/{self.project_number}/locations/{self.location}:retrieveContexts"
        
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": {"text": query},
            "vertex_rag_store": {
                "rag_corpora": [corpus_name]
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
    
    def _get_source_key(self, ctx: Dict) -> str:
        """Get a unique key for a context source (for deduplication/grouping)"""
        source = ctx.get("source", "")
        source_type = ctx.get("source_type", "local")
        
        if source_type == "wikem":
            # gs://bucket/processed/Topic.md → wikem-Topic
            parts = source.replace("gs://", "").split("/")
            filename = parts[-1] if parts else "unknown"
            return f"wikem-{filename.replace('.md', '')}"
        elif source_type == "pmc":
            # gs://bucket/processed/PMC8123456.md → pmc-PMC8123456
            parts = source.replace("gs://", "").split("/")
            filename = parts[-1] if parts else "unknown"
            return f"pmc-{filename.replace('.md', '')}"
        else:
            # gs://bucket/enterprise/ed/bundle/protocol_id/extracted_text.txt → protocol_id
            parts = source.replace("gs://", "").split("/")
            if len(parts) >= 6:
                return parts[4]  # protocol_id in new format
            elif len(parts) >= 5:
                return parts[3]  # protocol_id in legacy format
            return source

    def _generate_answer(self, query: str, contexts: List[Dict]) -> str:
        """Generate answer using Gemini with source-aware context"""
        # Group contexts by source protocol so citation numbers match displayed sources
        from collections import OrderedDict
        grouped = OrderedDict()
        for c in contexts[:5]:
            key = self._get_source_key(c)
            if key not in grouped:
                grouped[key] = {
                    "source_type": c.get("source_type", "local"),
                    "texts": []
                }
            grouped[key]["texts"].append(c["text"][:4000])
        
        # Build context string with deduplicated source numbers
        context_parts = []
        for i, (key, group) in enumerate(grouped.items()):
            source_type = group["source_type"]
            if source_type == "wikem":
                source_label = "WikEM"
            elif source_type == "pmc":
                source_label = "PMC Literature"
            else:
                source_label = "Local Protocol"
            
            combined_text = "\n".join(group["texts"])
            context_parts.append(f"[{i+1}] ({source_label}) {combined_text}")
        context_text = "\n---\n".join(context_parts)
        
        # Gemini endpoint (us-central1 for low latency)
        url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{self.project_id}/locations/us-central1/publishers/google/models/gemini-2.0-flash:generateContent"
        
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json"
        }
        
        prompt = f"""You are an emergency medicine clinical assistant for ED physicians.

CRITICAL RULES:
1. Answer the user's SPECIFIC QUESTION directly. Do NOT summarize the entire document.
2. ONLY use information from the provided context. Do NOT add outside medical knowledge.
3. If the context does not contain enough information to answer the question, say so clearly.
4. Add [1], [2] etc. citation numbers matching the context sources used.

FORMAT:
- Use markdown: **bold** for headers/drug names, "- " for bullets, blank lines between sections
- Prefer concise bullet points for quick ED reference
- Keep answers as short as the question requires — a simple question gets a short answer, a complex question gets a thorough answer
- Start with a bold header, then 1 sentence summary, then bullets if needed

CONTEXT:
{context_text}

QUESTION: {query}

ANSWER:"""

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1000
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            raise Exception(f"Gemini generation failed: {response.status_code} - {response.text}")
        
        result = response.json()
        return result["candidates"][0]["content"]["parts"][0]["text"]
    
    def _get_protocol_metadata(self, source_uri: str) -> Optional[Dict]:
        """Get metadata for a protocol from its source URI"""
        # Parse source URI to get enterprise_id, ed_id, bundle_id, and protocol_id
        # Format: gs://bucket/enterprise_id/ed_id/bundle_id/protocol_id/extracted_text.txt
        try:
            if source_uri.startswith("gs://"):
                parts = source_uri.split("/")
                if len(parts) >= 7:
                    # New format: bucket/enterprise_id/ed_id/bundle_id/protocol_id/extracted_text.txt
                    enterprise_id = parts[3]
                    ed_id = parts[4]
                    bundle_id = parts[5]
                    protocol_id = parts[6]
                    
                    cache_key = f"{enterprise_id}/{ed_id}/{bundle_id}/{protocol_id}"
                    if cache_key in self._metadata_cache:
                        return self._metadata_cache[cache_key]
                    
                    bucket = self.storage_client.bucket(PROCESSED_BUCKET)
                    blob = bucket.blob(f"{enterprise_id}/{ed_id}/{bundle_id}/{protocol_id}/metadata.json")
                    
                    if blob.exists():
                        content = blob.download_as_string()
                        metadata = json.loads(content)
                        self._metadata_cache[cache_key] = metadata
                        return metadata
                elif len(parts) >= 6:
                    # Legacy format with bundle: bucket/org_id/bundle_id/protocol_id/extracted_text.txt
                    org_id = parts[3]
                    bundle_id = parts[4]
                    protocol_id = parts[5]
                    
                    cache_key = f"{org_id}/{bundle_id}/{protocol_id}"
                    if cache_key in self._metadata_cache:
                        return self._metadata_cache[cache_key]
                    
                    bucket = self.storage_client.bucket(PROCESSED_BUCKET)
                    blob = bucket.blob(f"{org_id}/{bundle_id}/{protocol_id}/metadata.json")
                    
                    if blob.exists():
                        content = blob.download_as_string()
                        metadata = json.loads(content)
                        self._metadata_cache[cache_key] = metadata
                        return metadata
        except Exception as e:
            print(f"Error getting metadata for {source_uri}: {e}")
        
        return None
    
    def _get_wikem_metadata(self, source_uri: str) -> Optional[Dict]:
        """Get metadata for a WikEM topic from its source URI"""
        # Format: gs://clinical-assistant-457902-wikem/processed/Hyponatremia.md
        try:
            if source_uri.startswith("gs://"):
                parts = source_uri.split("/")
                filename = parts[-1] if parts else ""
                topic_slug = filename.replace(".md", "")
                
                cache_key = f"wikem/{topic_slug}"
                if cache_key in self._metadata_cache:
                    return self._metadata_cache[cache_key]
                
                bucket = self.storage_client.bucket(WIKEM_BUCKET)
                blob = bucket.blob(f"metadata/{topic_slug}.json")
                
                if blob.exists():
                    content = blob.download_as_string()
                    metadata = json.loads(content)
                    self._metadata_cache[cache_key] = metadata
                    return metadata
        except Exception as e:
            print(f"Error getting WikEM metadata for {source_uri}: {e}")
        
        return None

    def _get_pmc_metadata(self, source_uri: str) -> Optional[Dict]:
        """Get metadata for a PMC article from its source URI"""
        # Format: gs://clinical-assistant-457902-pmc/processed/PMC8123456.md
        try:
            if source_uri.startswith("gs://"):
                parts = source_uri.split("/")
                filename = parts[-1] if parts else ""
                pmcid = filename.replace(".md", "")
                
                cache_key = f"pmc/{pmcid}"
                if cache_key in self._metadata_cache:
                    return self._metadata_cache[cache_key]
                
                bucket = self.storage_client.bucket(PMC_BUCKET)
                blob = bucket.blob(f"metadata/{pmcid}.json")
                
                if blob.exists():
                    content = blob.download_as_string()
                    metadata = json.loads(content)
                    self._metadata_cache[cache_key] = metadata
                    return metadata
        except Exception as e:
            print(f"Error getting PMC metadata for {source_uri}: {e}")
        
        return None

    def _get_images_from_contexts(self, contexts: List[Dict]) -> List[Dict]:
        """Extract images from context sources - maintains protocol relevance order"""
        seen_images = set()
        images = []
        
        # Process contexts in order (most relevant first)
        for ctx_idx, ctx in enumerate(contexts):
            source_type = ctx.get("source_type", "local")
            
            if source_type == "wikem":
                # Get WikEM metadata with image URLs
                metadata = self._get_wikem_metadata(ctx["source"])
                if metadata:
                    for img in metadata.get("images", []):
                        img_url = img.get("url", "")
                        if img_url and img_url not in seen_images:
                            seen_images.add(img_url)
                            images.append({
                                "page": img.get("page", 0),
                                "url": img_url,
                                "source": f"WikEM: {metadata.get('title', metadata.get('protocol_id', 'unknown'))}",
                                "protocol_rank": ctx_idx
                            })
            elif source_type == "pmc":
                # Get PMC metadata with image URLs  
                metadata = self._get_pmc_metadata(ctx["source"])
                if metadata:
                    for img in metadata.get("images", []):
                        img_url = img.get("url", "")
                        if img_url and img_url not in seen_images:
                            seen_images.add(img_url)
                            images.append({
                                "page": img.get("page", 0),
                                "url": img_url,
                                "source": f"PMC: {metadata.get('title', metadata.get('pmcid', 'unknown'))}",
                                "protocol_rank": ctx_idx
                            })
            else:
                # Local protocol metadata
                metadata = self._get_protocol_metadata(ctx["source"])
                
                if metadata:
                    protocol_images = []
                    for img in metadata.get("images", []):
                        img_key = img.get("gcs_uri", "")
                        if img_key and img_key not in seen_images:
                            seen_images.add(img_key)
                            
                            # Convert to public URL
                            url = img_key.replace(
                                "gs://",
                                "https://storage.googleapis.com/"
                            )
                            
                            protocol_images.append({
                                "page": img.get("page", 0),
                                "url": url,
                                "source": metadata.get("protocol_id", "unknown"),
                                "protocol_rank": ctx_idx  # Track source protocol order
                            })
                    
                    # Sort this protocol's images by page number
                    protocol_images.sort(key=lambda x: x["page"])
                    images.extend(protocol_images)
        
        return images
    
    def _retrieve_multi_source(self, query: str, sources: List[str] = None) -> List[Dict]:
        """
        Retrieve contexts from multiple corpora in parallel.
        Each context is tagged with source_type ('local', 'wikem', or 'pmc').
        Results are merged and sorted by relevance score.
        """
        if sources is None:
            sources = ["local", "wikem"]
        
        all_contexts: List[Dict] = []
        
        def fetch_local():
            try:
                contexts = self._retrieve_contexts(query, self.corpus_name)
                for ctx in contexts:
                    ctx["source_type"] = "local"
                return contexts
            except Exception as e:
                print(f"Local corpus query failed: {e}")
                return []
        
        def fetch_wikem():
            try:
                contexts = self._retrieve_contexts(query, self.wikem_corpus_name)
                for ctx in contexts:
                    ctx["source_type"] = "wikem"
                return contexts
            except Exception as e:
                print(f"WikEM corpus query failed: {e}")
                return []
        
        def fetch_pmc():
            try:
                if self.pmc_corpus_name:
                    contexts = self._retrieve_contexts(query, self.pmc_corpus_name)
                    for ctx in contexts:
                        ctx["source_type"] = "pmc"
                    return contexts
                return []
            except Exception as e:
                print(f"PMC corpus query failed: {e}")
                return []
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            if "local" in sources:
                futures["local"] = executor.submit(fetch_local)
            if "wikem" in sources:
                futures["wikem"] = executor.submit(fetch_wikem)
            if "pmc" in sources:
                futures["pmc"] = executor.submit(fetch_pmc)
            
            for key, future in futures.items():
                try:
                    results = future.result(timeout=10)
                    all_contexts.extend(results)
                except Exception as e:
                    print(f"Failed to get {key} results: {e}")
        
        # Sort by score (lower = more relevant in Vertex AI RAG)
        all_contexts.sort(key=lambda x: x.get("score", 1))
        
        return all_contexts

    def query(self, query: str, include_images: bool = True, sources: List[str] = None,
              pmc_journals: List[str] = None,
              enterprise_id: str = None, ed_ids: List[str] = None, bundle_ids: List[str] = None) -> Dict:
        """
        Execute a full RAG query with multi-source retrieval
        
        Args:
            query: The search query
            include_images: Whether to include protocol images
            sources: List of sources to query ('local', 'wikem', 'pmc'). Default: ['local', 'wikem'].
            pmc_journals: Optional list of PMC journal names to keep. None = no filter (all journals).
            enterprise_id: Enterprise ID for path-prefix filtering
            ed_ids: List of ED IDs to filter by
            bundle_ids: List of bundle IDs to filter by
        
        Returns:
            dict with answer, images, citations
        """
        # Step 1: Retrieve contexts from all corpora in parallel
        contexts = self._retrieve_multi_source(query, sources)
        
        if not contexts:
            return {
                "answer": "No relevant protocols found for this query.",
                "images": [],
                "citations": []
            }
        
        # Step 1.5a: Filter PMC contexts by journal if a journal filter is provided
        if pmc_journals is not None:
            journal_set = set(pmc_journals)
            filtered = []
            for ctx in contexts:
                if ctx.get("source_type") != "pmc":
                    filtered.append(ctx)
                    continue
                # Look up the journal from GCS metadata
                metadata = self._get_pmc_metadata(ctx.get("source", ""))
                if metadata and metadata.get("journal") in journal_set:
                    filtered.append(ctx)
                elif not metadata:
                    # If we can't resolve metadata, keep the result (fail-open)
                    filtered.append(ctx)
            contexts = filtered
        
        # Step 1.5b: Filter local contexts by ED/bundle path prefixes
        if enterprise_id and ed_ids:
            prefixes = []
            for ed_id in ed_ids:
                if bundle_ids and "all" not in bundle_ids:
                    for bundle_id in bundle_ids:
                        prefixes.append(f"{enterprise_id}/{ed_id}/{bundle_id}/")
                else:
                    prefixes.append(f"{enterprise_id}/{ed_id}/")
            
            filtered_contexts = []
            for ctx in contexts:
                if ctx.get("source_type") in ("wikem", "pmc"):
                    # Always keep WikEM and PMC results (not filtered by ED path)
                    filtered_contexts.append(ctx)
                elif any(prefix in ctx.get("source", "") for prefix in prefixes):
                    filtered_contexts.append(ctx)
            
            contexts = filtered_contexts
            
            if not contexts:
                return {
                    "answer": "No relevant protocols found for the selected EDs and bundles.",
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
                "score": ctx["score"],
                "source_type": ctx.get("source_type", "local")
            }
            for ctx in contexts
        ]
        
        return {
            "answer": answer,
            "images": images,
            "citations": citations
        }
