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
PMC_CORPUS_ID = os.environ.get("PMC_CORPUS_ID", "7377459139586293760")
LITFL_CORPUS_ID = os.environ.get("LITFL_CORPUS_ID", "7991637538768945152")
REBELEM_CORPUS_ID = os.environ.get("REBELEM_CORPUS_ID", "1152921504606846976")
ALIEM_CORPUS_ID = os.environ.get("ALIEM_CORPUS_ID", "4611686018427387904")
PERSONAL_CORPUS_ID = os.environ.get("PERSONAL_CORPUS_ID", "2842897264777625600")
PROCESSED_BUCKET = f"{PROJECT_ID}-protocols-processed"
WIKEM_BUCKET = f"{PROJECT_ID}-wikem"
PMC_BUCKET = f"{PROJECT_ID}-pmc"
LITFL_BUCKET = f"{PROJECT_ID}-litfl"
REBELEM_BUCKET = f"{PROJECT_ID}-rebelem"
ALIEM_BUCKET = f"{PROJECT_ID}-aliem"
PERSONAL_BUCKET = os.environ.get("PERSONAL_BUCKET", f"{PROJECT_ID}-personal")


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
        self.personal_corpus_id = PERSONAL_CORPUS_ID
        self.corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{CORPUS_ID}"
        self.wikem_corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{WIKEM_CORPUS_ID}"
        self.pmc_corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{PMC_CORPUS_ID}" if PMC_CORPUS_ID else None
        self.litfl_corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{LITFL_CORPUS_ID}" if LITFL_CORPUS_ID else None
        self.rebelem_corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{REBELEM_CORPUS_ID}" if REBELEM_CORPUS_ID else None
        self.aliem_corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{ALIEM_CORPUS_ID}" if ALIEM_CORPUS_ID else None
        self.personal_corpus_name = f"projects/{PROJECT_NUMBER}/locations/{RAG_LOCATION}/ragCorpora/{PERSONAL_CORPUS_ID}" if PERSONAL_CORPUS_ID else None
        self.storage_client = storage.Client()
        self._metadata_cache = {}
    
    def _get_access_token(self) -> str:
        """Get OAuth2 access token"""
        credentials, _ = google.auth.default()
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        return credentials.token
    
    def _retrieve_contexts(self, query: str, corpus_name: str = None, top_k: int = 5) -> List[Dict]:
        """Retrieve relevant contexts from a RAG corpus.
        
        Args:
            query: Search query text
            corpus_name: RAG corpus resource name
            top_k: Maximum number of results to return (sent as similarityTopK)
        """
        if corpus_name is None:
            corpus_name = self.corpus_name
            
        url = f"https://{self.location}-aiplatform.googleapis.com/v1beta1/projects/{self.project_number}/locations/{self.location}:retrieveContexts"
        
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": {"text": query, "similarityTopK": top_k},
            "vertex_rag_store": {"rag_corpora": [corpus_name]}
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
        elif source_type == "personal":
            # gs://bucket/{uid}/{file_id}.txt → personal-{file_id}
            parts = source.replace("gs://", "").split("/")
            filename = parts[-1] if parts else "unknown"
            return f"personal-{filename.replace('.txt', '')}"
        else:
            # gs://bucket/enterprise/ed/bundle/protocol_id/extracted_text.txt → protocol_id
            parts = source.replace("gs://", "").split("/")
            if len(parts) >= 6:
                return parts[4]  # protocol_id in new format
            elif len(parts) >= 5:
                return parts[3]  # protocol_id in legacy format
            return source

    def _allocate_slots(self, contexts: List[Dict], max_total: int = 15) -> List[Dict]:
        """
        Category-aware slot allocator.

        Buckets contexts into 4 categories (local, personal, foam, literature),
        allocates slots proportionally based on which categories have results,
        then returns contexts ordered by category priority (local → personal →
        foam → literature), with best-scoring results first within each category.

        Per-source chunk caps:
          - local / personal: up to 3 chunks per unique source
          - foam / literature: 1 chunk per unique article

        Contexts must already be sorted by score ascending (lower = better).
        """
        if not contexts:
            return []

        from collections import OrderedDict
        import math

        # --- Category definitions ---
        FOAM_TYPES = {"wikem", "litfl", "rebelem", "aliem"}
        CATEGORY_ORDER = ["local", "personal", "foam", "literature"]
        BASE_WEIGHTS = {"local": 5, "personal": 3, "foam": 5, "literature": 5}
        MAX_CHUNKS_PER_SOURCE = {"local": 3, "personal": 3, "foam": 1, "literature": 1}

        def _category(ctx):
            st = ctx.get("source_type", "local")
            if st in FOAM_TYPES:
                return "foam"
            if st == "pmc":
                return "literature"
            if st == "personal":
                return "personal"
            return "local"

        # --- Bucket contexts by category ---
        buckets = {cat: [] for cat in CATEGORY_ORDER}
        for ctx in contexts:
            buckets[_category(ctx)].append(ctx)

        # --- Deduplicate within each bucket (best chunks per unique source) ---
        def _pick_best(bucket_contexts, chunk_cap):
            """Pick best unique-source chunks, up to chunk_cap per source."""
            picked = []
            source_counts: OrderedDict = OrderedDict()
            for ctx in bucket_contexts:          # already score-sorted
                key = self._get_source_key(ctx)
                cnt = source_counts.get(key, 0)
                if cnt >= chunk_cap:
                    continue
                source_counts[key] = cnt + 1
                picked.append(ctx)
            return picked

        deduped = {}
        for cat in CATEGORY_ORDER:
            deduped[cat] = _pick_best(buckets[cat], MAX_CHUNKS_PER_SOURCE[cat])

        # --- Compute proportional slot budgets ---
        active_cats = [cat for cat in CATEGORY_ORDER if deduped[cat]]
        if not active_cats:
            return []

        active_weight = sum(BASE_WEIGHTS[cat] for cat in active_cats)
        budgets = {}
        allocated = 0
        for i, cat in enumerate(active_cats):
            if i == len(active_cats) - 1:
                # Last category gets remainder to avoid rounding drift
                budgets[cat] = max_total - allocated
            else:
                budgets[cat] = math.floor(BASE_WEIGHTS[cat] / active_weight * max_total)
                allocated += budgets[cat]

        # --- Fill slots per category (capped at budget or available) ---
        result = []
        for cat in CATEGORY_ORDER:
            budget = budgets.get(cat, 0)
            chosen = deduped[cat][:budget]
            result.extend(chosen)

        # --- Log allocation for debugging ---
        parts = []
        for cat in CATEGORY_ORDER:
            budget = budgets.get(cat, 0)
            used = len([c for c in result if _category(c) == cat])
            if budget > 0 or used > 0:
                parts.append(f"{cat}={used}/{budget}")
        print(f"[rag-slots] {' '.join(parts)} total={len(result)}/{max_total}")

        return result

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
            elif source_type == "personal":
                source_label = "User Upload"
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
5. SOURCE PRIORITY: If a "Local Protocol" or "User Upload" source is present in the context, draw your primary answer from it. External sources (WikEM, PMC Literature, LITFL, REBEL EM, ALiEM) should only supplement or clarify — never override the local protocol's guidance.

RESPONSE FORMAT:

**Bottom Line:** Start with 1-2 sentences giving the most critical actionable answer. A physician glancing at this line alone should get what they need.

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
- Use markdown tables for dosing, scoring, and side-by-side comparisons. Keep tables compact with short column widths.
- Use bullet lists for criteria, differentials, and contraindications
- Use blank lines between sections for readability
- Be concise — only expand when clinical complexity demands it. A simple question gets a short answer.
- Keep the total answer under 1500 words. Prioritize the most critical information.
- IMPORTANT: When using markdown tables, use EXACTLY this format with single dashes:
  | Drug | Dose | Route | Notes |
  |------|------|-------|-------|
  | Calcium Chloride | 1g IV | IV | Fast onset |
  Do NOT use extra dashes, spaces, or long separator lines. Keep separators minimal.

CONTEXT:
{context_text}

QUESTION: {query}

ANSWER:"""
        return prompt, context_text

    def _generate_answer(self, query: str, contexts: List[Dict]) -> str:
        """Generate answer using Gemini (non-streaming)."""
        prompt, _ = self._build_prompt_and_context(query, contexts)
        
        url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{self.project_id}/locations/us-central1/publishers/google/models/gemini-2.5-flash:generateContent"
        
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json"
        }

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 8192
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

        url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{self.project_id}/locations/us-central1/publishers/google/models/gemini-2.5-flash:streamGenerateContent?alt=sse"

        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json"
        }

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 8192
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

    def _sign_personal_blob(self, blob, expiration_hours: int = 1) -> str:
        """Generate a signed URL for a personal file blob.
        Works on Cloud Run by using IAM signBlob API with compute credentials."""
        import datetime
        from google.auth import default as _auth_default
        from google.auth.transport import requests as _auth_requests
        from google.auth import iam as _iam
        from google.auth import credentials as _creds
        import google.oauth2.service_account

        credentials, _ = _auth_default()
        auth_req = _auth_requests.Request()
        credentials.refresh(auth_req)

        # On Cloud Run, use IAM signBlob to create a signer
        sa_email = credentials.service_account_email
        signer = _iam.Signer(
            request=auth_req,
            credentials=credentials,
            service_account_email=sa_email,
        )
        signing_creds = google.oauth2.service_account.Credentials(
            signer=signer,
            service_account_email=sa_email,
            token_uri="https://oauth2.googleapis.com/token",
        )

        return blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(hours=expiration_hours),
            method="GET",
            credentials=signing_creds,
        )

    def _get_personal_images(self, source_uri: str, matched_pages: List[int] = None) -> List[Dict]:
        """Render page images ON-DEMAND for a personal file.

        Downloads the original PDF from GCS, renders only the matched pages
        (≤5) at 100 DPI, uploads as public PNGs, and returns public URLs —
        same pattern as WikEM/LITFL images.

        source_uri format: gs://clinical-assistant-457902-personal/{uid}/{file_id}.txt
        """
        try:
            parts = source_uri.replace("gs://", "").split("/")
            if len(parts) < 3:
                return []
            uid = parts[1]
            file_id = parts[2].replace(".txt", "")

            # Cache key includes matched pages so repeated calls are free
            pages_key = ",".join(str(p) for p in sorted(matched_pages)) if matched_pages else "default"
            cache_key = f"personal/{uid}/{file_id}/{pages_key}"
            if cache_key in self._metadata_cache:
                return self._metadata_cache[cache_key]

            from google.cloud import firestore as _fs
            db = _fs.Client()

            doc = db.collection("users").document(uid).collection("personal_files").document(file_id).get()
            if not doc.exists:
                return []
            data = doc.to_dict()
            filename = data.get("filename", file_id)
            content_type = data.get("content_type", "application/pdf")

            bucket = self.storage_client.bucket(PERSONAL_BUCKET)
            result = []

            # ── Image uploads: return signed URL to the original ──
            if content_type and content_type.startswith("image/"):
                blob = bucket.blob(f"{uid}/{file_id}.original")
                if blob.exists():
                    signed_url = self._sign_personal_blob(blob)
                    result.append({
                        "page": 1,
                        "url": signed_url,
                        "source": f"📁 {filename}",
                    })
                self._metadata_cache[cache_key] = result
                return result

            # ── PDF uploads: render matched pages on-demand ──
            if content_type != "application/pdf":
                # Text / markdown files have no visual pages
                self._metadata_cache[cache_key] = []
                return []

            # Determine which pages to render (cap at 5)
            pages_to_render = sorted(matched_pages)[:5] if matched_pages else [1]
            if not matched_pages:
                print(f"Warning: no page markers found for {file_id}, defaulting to page 1")
            else:
                print(f"Personal PDF {file_id}: rendering pages {pages_to_render}")

            # Download the original PDF bytes from GCS
            original_blob = bucket.blob(f"{uid}/{file_id}.original")
            if not original_blob.exists():
                print(f"Original PDF not found in GCS for {file_id}")
                self._metadata_cache[cache_key] = []
                return []

            pdf_bytes = original_blob.download_as_bytes()

            import fitz  # PyMuPDF
            try:
                pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            except Exception as e:
                print(f"Failed to open PDF for on-demand rendering: {e}")
                self._metadata_cache[cache_key] = []
                return []

            try:
                total_pages = len(pdf_doc)
                for page_num in pages_to_render:
                    if page_num < 1 or page_num > total_pages:
                        continue
                    try:
                        page = pdf_doc[page_num - 1]  # 0-indexed
                        pix = page.get_pixmap(dpi=100)
                        png_bytes = pix.tobytes("png")

                        # Upload rendered page to GCS and generate signed URL
                        blob_path = f"{uid}/{file_id}/page_{page_num}.png"
                        blob = bucket.blob(blob_path)
                        blob.upload_from_string(png_bytes, content_type="image/png")
                        signed_url = self._sign_personal_blob(blob)

                        result.append({
                            "page": page_num,
                            "url": signed_url,
                            "source": f"📁 {filename}",
                        })
                    except Exception as e:
                        print(f"Failed to render page {page_num} for {file_id}: {e}")
            finally:
                pdf_doc.close()

            self._metadata_cache[cache_key] = result
            return result

        except Exception as e:
            print(f"Error getting personal images for {source_uri}: {e}")
            return []

    def _get_images_from_contexts(self, contexts: List[Dict], all_contexts: List[Dict] = None) -> List[Dict]:
        """Extract images from context sources - maintains protocol relevance order.
        
        all_contexts: optional pre-dedup list so personal page numbers can be
        collected from every chunk that matched, not just the single surviving
        context after deduplication.
        """
        seen_images = set()
        images = []

        # Pre-collect ALL page numbers per personal source from every chunk
        # (before dedup threw the extras away).
        import re as _re
        personal_all_pages: Dict[str, List[int]] = {}
        for ctx in (all_contexts or contexts):
            if ctx.get("source_type") == "personal":
                src = ctx.get("source", "")
                pages = [int(m) for m in _re.findall(r'--- Page (\d+)', ctx.get("text", ""))]
                if pages:
                    personal_all_pages.setdefault(src, []).extend(pages)
        # Deduplicate & sort per source
        for src in personal_all_pages:
            personal_all_pages[src] = sorted(set(personal_all_pages[src]))
        
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
            elif source_type == "personal":
                # Use pre-collected pages from ALL chunks (not just this deduped one)
                matched_pages = personal_all_pages.get(ctx.get("source", ""), [])
                if not matched_pages:
                    # Fallback: parse from this single chunk
                    matched_pages = [int(m) for m in _re.findall(r'--- Page (\d+)', ctx.get("text", ""))]
                personal_images = self._get_personal_images(ctx["source"], matched_pages=matched_pages or None)
                for img in personal_images:
                    img_url = img.get("url", "")
                    if img_url and img_url not in seen_images:
                        seen_images.add(img_url)
                        images.append({
                            "page": img.get("page", 0),
                            "url": img_url,
                            "source": img.get("source", "My File"),
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
    
    def _retrieve_multi_source(self, query: str, sources: List[str] = None, personal_user_id: str = None) -> List[Dict]:
        """
        Retrieve contexts from multiple corpora in parallel.
        Each context is tagged with source_type ('local', 'wikem', 'pmc', 'personal', etc.).
        Results are merged and sorted by relevance score.
        """
        if sources is None:
            sources = ["local", "wikem"]
        
        all_contexts: List[Dict] = []
        
        def fetch_local():
            try:
                contexts = self._retrieve_contexts(query, self.corpus_name, top_k=5)
                for ctx in contexts:
                    ctx["source_type"] = "local"
                return contexts
            except Exception as e:
                print(f"Local corpus query failed: {e}")
                return []
        
        def fetch_wikem():
            try:
                contexts = self._retrieve_contexts(query, self.wikem_corpus_name, top_k=5)
                for ctx in contexts:
                    ctx["source_type"] = "wikem"
                return contexts
            except Exception as e:
                print(f"WikEM corpus query failed: {e}")
                return []
        
        def fetch_pmc():
            try:
                if self.pmc_corpus_name:
                    contexts = self._retrieve_contexts(query, self.pmc_corpus_name, top_k=5)
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
                    contexts = self._retrieve_contexts(query, self.litfl_corpus_name, top_k=5)
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
                    contexts = self._retrieve_contexts(query, self.rebelem_corpus_name, top_k=5)
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
                    contexts = self._retrieve_contexts(query, self.aliem_corpus_name, top_k=5)
                    for ctx in contexts:
                        ctx["source_type"] = "aliem"
                    return contexts
                return []
            except Exception as e:
                print(f"ALiEM corpus query failed: {e}")
                return []
        
        def fetch_personal():
            try:
                if self.personal_corpus_name and personal_user_id:
                    contexts = self._retrieve_contexts(query, self.personal_corpus_name, top_k=10)
                    # Filter to only this user's files
                    user_prefix = f"gs://{PERSONAL_BUCKET}/{personal_user_id}/"
                    user_contexts = [c for c in contexts if c.get("source", "").startswith(user_prefix)]
                    for ctx in user_contexts:
                        ctx["source_type"] = "personal"
                    return user_contexts[:5]
                return []
            except Exception as e:
                print(f"Personal corpus query failed: {e}")
                return []
        
        import time as _time
        with ThreadPoolExecutor(max_workers=7) as executor:
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
            if "personal" in sources and personal_user_id:
                futures["personal"] = executor.submit(fetch_personal)
            
            t0 = _time.time()
            for key, future in futures.items():
                try:
                    results = future.result(timeout=30)
                    elapsed = _time.time() - t0
                    print(f"[rag-timing] {key}: {len(results)} results in {elapsed:.2f}s")
                    all_contexts.extend(results)
                except Exception as e:
                    elapsed = _time.time() - t0
                    print(f"[rag-timing] {key}: FAILED in {elapsed:.2f}s — {type(e).__name__}: {e}")
        
        # Sort by score (lower = more relevant in Vertex AI RAG)
        all_contexts.sort(key=lambda x: x.get("score", 1))
        
        return all_contexts

    def query(self, query: str, include_images: bool = True, sources: List[str] = None,
              pmc_journals: List[str] = None,
              enterprise_id: str = None, ed_ids: List[str] = None, bundle_ids: List[str] = None,
              personal_user_id: str = None) -> Dict:
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
        contexts = self._retrieve_multi_source(query, sources, personal_user_id=personal_user_id)
        
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
                if ctx.get("source_type") in ("wikem", "pmc", "litfl", "rebelem", "aliem", "personal"):
                    # Always keep external/personal source results (not filtered by ED path)
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
        
        # Step 1.6: Allocate slots per category (local/personal/foam/literature)
        all_contexts = list(contexts)  # preserve pre-dedup for personal page collection
        contexts = self._allocate_slots(contexts)

        # Step 2: Generate answer with Gemini (fast, no grounding overhead)
        answer = self._generate_answer(query, contexts)
        
        # Step 3: Get images from contexts
        images = []
        if include_images:
            images = self._get_images_from_contexts(contexts, all_contexts=all_contexts)
        
        # Step 4: Build citations (order matches context order: local → personal → foam → literature)
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
                     enterprise_id: str = None, ed_ids: List[str] = None, bundle_ids: List[str] = None,
                     personal_user_id: str = None):
        """
        Execute a full RAG query with streaming answer generation.
        
        Yields dicts:
          {"type": "chunk", "text": "..."}      — incremental text
          {"type": "done", "citations": [...], "images": [...], "query_time_ms": N}
        """
        import time as _time
        start = _time.time()

        # Step 1: Retrieve contexts (same as non-streaming)
        contexts = self._retrieve_multi_source(query, sources, personal_user_id=personal_user_id)

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
                if ctx.get("source_type") in ("wikem", "pmc", "litfl", "rebelem", "aliem", "personal"):
                    filtered_contexts.append(ctx)
                elif any(prefix in ctx.get("source", "") for prefix in prefixes):
                    filtered_contexts.append(ctx)
            contexts = filtered_contexts

            if not contexts:
                yield {"type": "chunk", "text": "No relevant protocols found for the selected EDs and bundles."}
                yield {"type": "done", "citations": [], "images": [], "query_time_ms": int((_time.time() - start) * 1000)}
                return

        # Step 1.6: Allocate slots per category (local/personal/foam/literature)
        all_contexts = list(contexts)  # preserve pre-dedup for personal page collection
        contexts = self._allocate_slots(contexts)

        # Step 2: Stream answer from Gemini
        for text_chunk in self.generate_answer_stream(query, contexts):
            yield {"type": "chunk", "text": text_chunk}

        # Step 3: Get images
        images = []
        if include_images:
            images = self._get_images_from_contexts(contexts, all_contexts=all_contexts)

        # Step 4: Build citations (order matches context order: local → personal → foam → literature)
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
        url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{self.project_id}/locations/us-central1/publishers/google/models/gemini-2.5-flash:generateContent"

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
