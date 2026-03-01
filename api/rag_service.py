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
WIKEM_CORPUS_ID = os.environ.get("WIKEM_CORPUS_ID", "3379951520341557248")
PMC_CORPUS_ID = os.environ.get("PMC_CORPUS_ID", "6838716034162098176")
LITFL_CORPUS_ID = os.environ.get("LITFL_CORPUS_ID", "7991637538768945152")
REBELEM_CORPUS_ID = os.environ.get("REBELEM_CORPUS_ID", "1152921504606846976")
ALIEM_CORPUS_ID = os.environ.get("ALIEM_CORPUS_ID", "4611686018427387904")
PROCESSED_BUCKET = f"{PROJECT_ID}-protocols-processed"
WIKEM_BUCKET = f"{PROJECT_ID}-wikem"
PMC_BUCKET = f"{PROJECT_ID}-pmc"
LITFL_BUCKET = f"{PROJECT_ID}-litfl"
REBELEM_BUCKET = f"{PROJECT_ID}-rebelem"
ALIEM_BUCKET = f"{PROJECT_ID}-aliem"


class RAGService:
    """Service for RAG queries and answer generation"""
    
    def __init__(self):
        self.project_id = PROJECT_ID
        self.project_number = PROJECT_NUMBER
        self.location = RAG_LOCATION
        self.corpus_id = CORPUS_ID
        self.wikem_corpus_id = WIKEM_CORPUS_ID
        self.pmc_corpus_id = PMC_CORPUS_ID
        self.litfl_corpus_id = LITFL_CORPUS_ID
        self.rebelem_corpus_id = REBELEM_CORPUS_ID
        self.aliem_corpus_id = ALIEM_CORPUS_ID
        self.corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{CORPUS_ID}"
        self.wikem_corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{WIKEM_CORPUS_ID}"
        self.pmc_corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{PMC_CORPUS_ID}" if PMC_CORPUS_ID else None
        self.litfl_corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{LITFL_CORPUS_ID}" if LITFL_CORPUS_ID else None
        self.rebelem_corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{REBELEM_CORPUS_ID}" if REBELEM_CORPUS_ID else None
        self.aliem_corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{ALIEM_CORPUS_ID}" if ALIEM_CORPUS_ID else None
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
        elif source_type == "litfl":
            # gs://bucket/processed/topic-slug.md → litfl-topic-slug
            parts = source.replace("gs://", "").split("/")
            filename = parts[-1] if parts else "unknown"
            return f"litfl-{filename.replace('.md', '')}"
        elif source_type == "rebelem":
            # gs://bucket/processed/topic-slug.md → rebelem-topic-slug
            parts = source.replace("gs://", "").split("/")
            filename = parts[-1] if parts else "unknown"
            return f"rebelem-{filename.replace('.md', '')}"
        elif source_type == "aliem":
            # gs://bucket/processed/topic-slug.md → aliem-topic-slug
            parts = source.replace("gs://", "").split("/")
            filename = parts[-1] if parts else "unknown"
            return f"aliem-{filename.replace('.md', '')}"
        else:
            # gs://bucket/enterprise/ed/bundle/protocol_id/extracted_text.txt → protocol_id
            parts = source.replace("gs://", "").split("/")
            if len(parts) >= 6:
                return parts[4]  # protocol_id in new format
            elif len(parts) >= 5:
                return parts[3]  # protocol_id in legacy format
            return source

    def _filter_by_relevance(self, contexts: List[Dict], min_results: int = 5,
                              max_results: int = 10, score_multiplier: float = 4.0) -> List[Dict]:
        """
        Filter contexts using an adaptive relevance threshold.
        
        Uses the best score as an anchor and keeps contexts within
        score_multiplier × best_score. Deduplicates by source key.
        Returns between min_results and max_results unique sources.
        
        Contexts must already be sorted by score ascending (lower = better).
        """
        if not contexts:
            return []

        from collections import OrderedDict
        best_score = contexts[0].get("score", 0)
        # Guard against near-zero scores — use a floor so the cutoff isn't too tight
        cutoff = max(best_score * score_multiplier, 0.05)

        seen_keys = OrderedDict()
        for ctx in contexts:
            key = self._get_source_key(ctx)
            if key in seen_keys:
                continue  # already have this source (better-scored chunk)
            # Always include up to min_results unique sources
            if len(seen_keys) < min_results:
                seen_keys[key] = ctx
            # Beyond min, only include if within the relevance cutoff and under max
            elif ctx.get("score", 1) <= cutoff and len(seen_keys) < max_results:
                seen_keys[key] = ctx
            # Stop once we hit max
            if len(seen_keys) >= max_results:
                break

        return list(seen_keys.values())

    def _build_prompt_and_context(self, query: str, contexts: List[Dict]) -> tuple[str, str]:
        """Build the prompt and context text for Gemini. Returns (prompt, context_text)."""
        from collections import OrderedDict
        grouped = OrderedDict()
        for c in contexts:
            key = self._get_source_key(c)
            if key not in grouped:
                grouped[key] = {
                    "source_type": c.get("source_type", "local"),
                    "texts": []
                }
            grouped[key]["texts"].append(c["text"][:4000])
        
        context_parts = []
        for i, (key, group) in enumerate(grouped.items()):
            source_type = group["source_type"]
            if source_type == "wikem":
                source_label = "WikEM"
            elif source_type == "pmc":
                source_label = "PMC Literature"
            elif source_type == "litfl":
                source_label = "LITFL"
            elif source_type == "rebelem":
                source_label = "REBEL EM"
            elif source_type == "aliem":
                source_label = "ALiEM"
            else:
                source_label = "Local Protocol"
            
            combined_text = "\n".join(group["texts"])
            context_parts.append(f"[{i+1}] ({source_label}) {combined_text}")
        context_text = "\n---\n".join(context_parts)
        
        prompt = f"""You are a clinical decision support tool for emergency medicine physicians, designed to give actionable advice at the bedside. You answer questions about both clinical topics AND local institutional protocols.

CRITICAL RULES:
1. Answer the user's SPECIFIC QUESTION directly. Do NOT summarize the entire document.
2. ONLY use information from the provided context. Do NOT add outside medical knowledge.
3. If the context does not contain enough information to answer the question, say so clearly.
4. Add [1], [2] etc. citation numbers inline throughout your answer matching the context sources used. Every factual claim should have a citation.

RESPONSE FORMAT:

🔴 **BOTTOM LINE:** Start with 1-2 sentences giving the most critical actionable answer. A physician glancing at this line alone should get what they need.

Then use the structure that best fits the question — pick from these as needed:

- **Dosing/Medications** → Use a markdown table: | Drug | Dose | Route | Notes |
- **Scoring tools / risk stratification** → Use a markdown table for criteria and scoring
- **Differential diagnosis** → Categorize (e.g., by system, acuity, or likelihood)
- **Contraindications** → Split into ABSOLUTE vs RELATIVE with bullet lists
- **Procedures / algorithms** → Numbered step-by-step
- **Local protocol questions** → Follow the protocol's own structure; quote key decision points and thresholds directly
- **Simple factual questions** → Answer in 1-3 sentences, no extra structure needed

FORMATTING RULES:
- Use **bold** for drug names, critical values, and section headers
- Use markdown tables (| col1 | col2 |) for dosing, scoring, and side-by-side comparisons — always include a header row and separator row
- Use bullet lists for criteria, differentials, and contraindications
- Use blank lines between sections for readability
- Be concise — only expand when clinical complexity demands it. A simple question gets a short answer.

CONTEXT:
{context_text}

QUESTION: {query}

ANSWER:"""
        return prompt, context_text

    def _generate_answer(self, query: str, contexts: List[Dict]) -> str:
        """Generate answer using Gemini (non-streaming)."""
        prompt, _ = self._build_prompt_and_context(query, contexts)
        
        url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{self.project_id}/locations/us-central1/publishers/google/models/gemini-2.0-flash:generateContent"
        
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json"
        }

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2000
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            raise Exception(f"Gemini generation failed: {response.status_code} - {response.text}")
        
        result = response.json()
        return result["candidates"][0]["content"]["parts"][0]["text"]

    def generate_answer_stream(self, query: str, contexts: List[Dict]):
        """Generate answer using Gemini with streaming. Yields text chunks."""
        prompt, _ = self._build_prompt_and_context(query, contexts)
        
        url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{self.project_id}/locations/us-central1/publishers/google/models/gemini-2.0-flash:streamGenerateContent?alt=sse"
        
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json"
        }

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2000
            }
        }
        
        response = requests.post(url, headers=headers, json=payload, stream=True)
        
        if response.status_code != 200:
            raise Exception(f"Gemini streaming failed: {response.status_code} - {response.text}")
        
        for line in response.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8")
            if line_str.startswith("data: "):
                json_str = line_str[6:]
                try:
                    chunk = json.loads(json_str)
                    candidates = chunk.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for part in parts:
                            text = part.get("text", "")
                            if text:
                                yield text
                except json.JSONDecodeError:
                    continue
    
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

    def _get_litfl_metadata(self, source_uri: str) -> Optional[Dict]:
        """Get metadata for a LITFL page from its source URI"""
        # Format: gs://clinical-assistant-457902-litfl/processed/topic-slug.md
        try:
            if source_uri.startswith("gs://"):
                parts = source_uri.split("/")
                filename = parts[-1] if parts else ""
                slug = filename.replace(".md", "")
                
                cache_key = f"litfl/{slug}"
                if cache_key in self._metadata_cache:
                    return self._metadata_cache[cache_key]
                
                bucket = self.storage_client.bucket(LITFL_BUCKET)
                blob = bucket.blob(f"metadata/{slug}.json")
                
                if blob.exists():
                    content = blob.download_as_string()
                    metadata = json.loads(content)
                    self._metadata_cache[cache_key] = metadata
                    return metadata
        except Exception as e:
            print(f"Error getting LITFL metadata for {source_uri}: {e}")
        
        return None

    def _get_rebelem_metadata(self, source_uri: str) -> Optional[Dict]:
        """Get metadata for a REBEL EM article from its source URI"""
        # Format: gs://clinical-assistant-457902-rebelem/processed/topic-slug.md
        try:
            if source_uri.startswith("gs://"):
                parts = source_uri.split("/")
                filename = parts[-1] if parts else ""
                slug = filename.replace(".md", "")
                
                cache_key = f"rebelem/{slug}"
                if cache_key in self._metadata_cache:
                    return self._metadata_cache[cache_key]
                
                bucket = self.storage_client.bucket(REBELEM_BUCKET)
                blob = bucket.blob(f"metadata/{slug}.json")
                
                if blob.exists():
                    content = blob.download_as_string()
                    metadata = json.loads(content)
                    self._metadata_cache[cache_key] = metadata
                    return metadata
        except Exception as e:
            print(f"Error getting REBEL EM metadata for {source_uri}: {e}")
        
        return None

    def _get_aliem_metadata(self, source_uri: str) -> Optional[Dict]:
        """Get metadata for an ALiEM article from its source URI"""
        # Format: gs://clinical-assistant-457902-aliem/processed/topic-slug.md
        try:
            if source_uri.startswith("gs://"):
                parts = source_uri.split("/")
                filename = parts[-1] if parts else ""
                slug = filename.replace(".md", "")
                
                cache_key = f"aliem/{slug}"
                if cache_key in self._metadata_cache:
                    return self._metadata_cache[cache_key]
                
                bucket = self.storage_client.bucket(ALIEM_BUCKET)
                blob = bucket.blob(f"metadata/{slug}.json")
                
                if blob.exists():
                    content = blob.download_as_string()
                    metadata = json.loads(content)
                    self._metadata_cache[cache_key] = metadata
                    return metadata
        except Exception as e:
            print(f"Error getting ALiEM metadata for {source_uri}: {e}")
        
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
            elif source_type == "litfl":
                # Get LITFL metadata with image URLs
                metadata = self._get_litfl_metadata(ctx["source"])
                if metadata:
                    for img in metadata.get("images", []):
                        img_url = img.get("gcs_public_url", img.get("url", ""))
                        if img_url and img_url not in seen_images:
                            seen_images.add(img_url)
                            images.append({
                                "page": img.get("page", 0),
                                "url": img_url,
                                "source": f"LITFL: {metadata.get('title', 'unknown')}",
                                "protocol_rank": ctx_idx
                            })
            elif source_type == "rebelem":
                # Get REBEL EM metadata with image URLs
                metadata = self._get_rebelem_metadata(ctx["source"])
                if metadata:
                    for img in metadata.get("images", []):
                        img_url = img.get("url", "")
                        if img_url and img_url not in seen_images:
                            seen_images.add(img_url)
                            images.append({
                                "page": img.get("page", 0),
                                "url": img_url,
                                "source": f"REBEL EM: {metadata.get('title', 'unknown')}",
                                "protocol_rank": ctx_idx
                            })
            elif source_type == "aliem":
                # Get ALiEM metadata with image URLs
                metadata = self._get_aliem_metadata(ctx["source"])
                if metadata:
                    for img in metadata.get("images", []):
                        img_url = img.get("url", "")
                        if img_url and img_url not in seen_images:
                            seen_images.add(img_url)
                            images.append({
                                "page": img.get("page", 0),
                                "url": img_url,
                                "source": f"ALiEM: {metadata.get('title', 'unknown')}",
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
        
        def fetch_litfl():
            try:
                if self.litfl_corpus_name:
                    contexts = self._retrieve_contexts(query, self.litfl_corpus_name)
                    for ctx in contexts:
                        ctx["source_type"] = "litfl"
                    return contexts
                return []
            except Exception as e:
                print(f"LITFL corpus query failed: {e}")
                return []
        
        def fetch_rebelem():
            try:
                if self.rebelem_corpus_name:
                    contexts = self._retrieve_contexts(query, self.rebelem_corpus_name)
                    for ctx in contexts:
                        ctx["source_type"] = "rebelem"
                    return contexts
                return []
            except Exception as e:
                print(f"REBEL EM corpus query failed: {e}")
                return []
        
        def fetch_aliem():
            try:
                if self.aliem_corpus_name:
                    contexts = self._retrieve_contexts(query, self.aliem_corpus_name)
                    for ctx in contexts:
                        ctx["source_type"] = "aliem"
                    return contexts
                return []
            except Exception as e:
                print(f"ALiEM corpus query failed: {e}")
                return []
        
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {}
            if "local" in sources:
                futures["local"] = executor.submit(fetch_local)
            if "wikem" in sources:
                futures["wikem"] = executor.submit(fetch_wikem)
            if "pmc" in sources:
                futures["pmc"] = executor.submit(fetch_pmc)
            if "litfl" in sources:
                futures["litfl"] = executor.submit(fetch_litfl)
            if "rebelem" in sources:
                futures["rebelem"] = executor.submit(fetch_rebelem)
            if "aliem" in sources:
                futures["aliem"] = executor.submit(fetch_aliem)
            
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
            sources: List of sources to query ('local', 'wikem', 'pmc', 'litfl'). Default: ['local', 'wikem'].
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
                if ctx.get("source_type") in ("wikem", "pmc", "litfl", "rebelem", "aliem"):
                    # Always keep external source results (not filtered by ED path)
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
        
        # Step 1.6: Apply adaptive relevance filter (min 5, max 10 unique sources)
        contexts = self._filter_by_relevance(contexts)

        # Step 2: Generate answer with Gemini (fast, no grounding overhead)
        answer = self._generate_answer(query, contexts)
        
        # Step 3: Get images from contexts
        images = []
        if include_images:
            images = self._get_images_from_contexts(contexts)
        
        # Step 4: Build citations (contexts already filtered + deduplicated)
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

    def query_stream(self, query: str, include_images: bool = True, sources: List[str] = None,
                     pmc_journals: List[str] = None,
                     enterprise_id: str = None, ed_ids: List[str] = None, bundle_ids: List[str] = None):
        """
        Execute a full RAG query with streaming answer generation.
        
        Yields dicts:
          {"type": "chunk", "text": "..."}      — incremental text
          {"type": "done", "citations": [...], "images": [...], "query_time_ms": N}
        """
        import time as _time
        start = _time.time()

        # Step 1: Retrieve contexts (same as non-streaming)
        contexts = self._retrieve_multi_source(query, sources)

        if not contexts:
            yield {"type": "chunk", "text": "No relevant protocols found for this query."}
            yield {"type": "done", "citations": [], "images": [], "query_time_ms": int((_time.time() - start) * 1000)}
            return

        # Step 1.5a: Filter PMC by journal
        if pmc_journals is not None:
            journal_set = set(pmc_journals)
            filtered = []
            for ctx in contexts:
                if ctx.get("source_type") != "pmc":
                    filtered.append(ctx)
                    continue
                metadata = self._get_pmc_metadata(ctx.get("source", ""))
                if metadata and metadata.get("journal") in journal_set:
                    filtered.append(ctx)
                elif not metadata:
                    filtered.append(ctx)
            contexts = filtered

        # Step 1.5b: Filter local by ED/bundle
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
                if ctx.get("source_type") in ("wikem", "pmc", "litfl", "rebelem", "aliem"):
                    filtered_contexts.append(ctx)
                elif any(prefix in ctx.get("source", "") for prefix in prefixes):
                    filtered_contexts.append(ctx)
            contexts = filtered_contexts

            if not contexts:
                yield {"type": "chunk", "text": "No relevant protocols found for the selected EDs and bundles."}
                yield {"type": "done", "citations": [], "images": [], "query_time_ms": int((_time.time() - start) * 1000)}
                return

        # Step 1.6: Apply adaptive relevance filter (min 5, max 10 unique sources)
        contexts = self._filter_by_relevance(contexts)

        # Step 2: Stream answer from Gemini
        for text_chunk in self.generate_answer_stream(query, contexts):
            yield {"type": "chunk", "text": text_chunk}

        # Step 3: Get images
        images = []
        if include_images:
            images = self._get_images_from_contexts(contexts)

        # Step 4: Build citations (contexts already filtered + deduplicated)
        citations = [
            {
                "source": ctx["source"],
                "score": ctx["score"],
                "source_type": ctx.get("source_type", "local")
            }
            for ctx in contexts
        ]

        query_time_ms = int((_time.time() - start) * 1000)
        yield {"type": "done", "citations": citations, "images": images, "query_time_ms": query_time_ms}

    def protocol_summary_stream(self, query: str, enterprise_id: str,
                                 ed_ids: List[str] = None, bundle_ids: List[str] = None,
                                 top_k: int = 5):
        """
        Protocol Summary mode: retrieve matching local protocol chunks,
        group by protocol, generate a Gemini summary per protocol, and
        stream results card-by-card via SSE events.

        Yields dicts:
          {"type": "protocol_card", ...}   — one per matched protocol
          {"type": "done", "total_protocols": N, "query_time_ms": N}
          {"type": "error", "message": "..."}
        """
        import time as _time
        from collections import defaultdict
        start = _time.time()

        # Step 1: Retrieve from local corpus only
        try:
            contexts = self._retrieve_contexts(query, self.corpus_name)
            for ctx in contexts:
                ctx["source_type"] = "local"
        except Exception as e:
            yield {"type": "error", "message": f"RAG retrieval failed: {str(e)}"}
            return

        # Step 2: Filter by enterprise/ED/bundle path prefixes
        if enterprise_id and ed_ids:
            prefixes = []
            for ed_id in ed_ids:
                if bundle_ids and "all" not in bundle_ids:
                    for bundle_id in bundle_ids:
                        prefixes.append(f"{enterprise_id}/{ed_id}/{bundle_id}/")
                else:
                    prefixes.append(f"{enterprise_id}/{ed_id}/")
            contexts = [ctx for ctx in contexts if any(p in ctx.get("source", "") for p in prefixes)]
        elif enterprise_id:
            contexts = [ctx for ctx in contexts if enterprise_id in ctx.get("source", "")]

        if not contexts:
            yield {"type": "error", "message": "No matching local protocols found for your query and selected EDs."}
            return

        # Step 3: Group chunks by protocol_id
        protocol_chunks = defaultdict(lambda: {"chunks": [], "max_score": 0.0, "source": ""})

        for ctx in contexts:
            source = ctx.get("source", "")
            parts = source.replace("gs://", "").split("/")

            # Parse: bucket/enterprise/ed/bundle/protocol_id/extracted_text.txt
            if len(parts) >= 6:
                ent_id, ed_id_part, bundle_id_part, protocol_id = parts[1], parts[2], parts[3], parts[4]
            elif len(parts) >= 5:
                ent_id, ed_id_part, bundle_id_part, protocol_id = parts[1], None, parts[2], parts[3]
            else:
                continue

            if protocol_id == "extracted_text":
                continue

            key = f"{ent_id}/{ed_id_part or 'default'}/{bundle_id_part}/{protocol_id}"
            entry = protocol_chunks[key]
            entry["chunks"].append({"text": ctx.get("text", ""), "score": ctx.get("score", 1.0)})
            if ctx.get("score", 1.0) < entry["max_score"] or entry["max_score"] == 0.0:
                entry["max_score"] = ctx.get("score", 1.0)
            entry["source"] = source
            entry["enterprise_id"] = ent_id
            entry["ed_id"] = ed_id_part
            entry["bundle_id"] = bundle_id_part
            entry["protocol_id"] = protocol_id

        if not protocol_chunks:
            yield {"type": "error", "message": "No matching local protocols found."}
            return

        # Step 4: Rank by best score (lower = more relevant in Vertex AI RAG) and take top_k
        ranked = sorted(protocol_chunks.values(), key=lambda p: p["max_score"])[:top_k]

        # Step 4.5: Apply adaptive relevance threshold to drop low-relevance cards
        if ranked:
            best_score = ranked[0]["max_score"]
            cutoff = max(best_score * 4.0, 0.05)
            ranked = [p for p in ranked if p["max_score"] <= cutoff]

        if not ranked:
            yield {"type": "error", "message": "No sufficiently relevant protocols found for your query."}
            return

        # Step 5: Generate a contextual summary per protocol with Gemini and stream cards
        for proto in ranked:
            chunk_texts = "\n\n---\n\n".join([c["text"][:3000] for c in proto["chunks"][:5]])
            protocol_id = proto["protocol_id"]

            summary_prompt = f"""You are an emergency medicine protocol assistant. A clinician asked: "{query}"

The following excerpts are from a local ED protocol called "{protocol_id}":

{chunk_texts}

Write a concise 2-3 sentence summary of what this protocol covers and how it relates to the clinician's question. Encourage them to review the full protocol for specific clinical guidance. Do not fabricate clinical recommendations beyond what the excerpts contain."""

            try:
                summary = self._generate_summary(summary_prompt)
            except Exception:
                summary = "Protocol relevant to your query. Review the full document for details."

            # Build PDF URL
            ent_id = proto["enterprise_id"]
            ed_id_part = proto.get("ed_id")
            bundle_id_part = proto["bundle_id"]
            if ed_id_part:
                pdf_url = f"https://storage.googleapis.com/clinical-assistant-457902-protocols-raw/{ent_id}/{ed_id_part}/{bundle_id_part}/{protocol_id}.pdf"
            else:
                pdf_url = f"https://storage.googleapis.com/clinical-assistant-457902-protocols-raw/{ent_id}/{bundle_id_part}/{protocol_id}.pdf"

            # Get images from protocol metadata
            images = []
            try:
                metadata = self._get_protocol_metadata(proto["source"])
                if metadata:
                    for img in metadata.get("images", []):
                        gcs_uri = img.get("gcs_uri", "")
                        if gcs_uri:
                            images.append({
                                "page": img.get("page", 0),
                                "url": gcs_uri.replace("gs://", "https://storage.googleapis.com/")
                            })
                    images.sort(key=lambda x: x["page"])
            except Exception:
                pass

            yield {
                "type": "protocol_card",
                "protocol_id": protocol_id,
                "enterprise_id": ent_id,
                "ed_id": ed_id_part,
                "bundle_id": bundle_id_part,
                "summary": summary,
                "pdf_url": pdf_url,
                "images": images,
                "relevance_score": round(proto["max_score"], 4),
            }

        elapsed = int((_time.time() - start) * 1000)
        yield {"type": "done", "total_protocols": len(ranked), "query_time_ms": elapsed}

    def _generate_summary(self, prompt: str) -> str:
        """Generate a short summary with Gemini (non-streaming, low token count)."""
        url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{self.project_id}/locations/us-central1/publishers/google/models/gemini-2.0-flash:generateContent"

        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json"
        }

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 300
            }
        }

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            raise Exception(f"Gemini summary generation failed: {response.status_code}")

        result = response.json()
        return result["candidates"][0]["content"]["parts"][0]["text"].strip()
