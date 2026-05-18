"""Grounded Gemini Search service for the pilot general-clinical route."""

import json
import os
import time
from typing import Dict, Generator, List, Optional
from urllib.parse import urlparse

import google.auth
import google.auth.transport.requests
import requests


PROJECT_ID = os.environ.get("PROJECT_ID", "clinical-assistant-457902")
GEMINI_SEARCH_LOCATION = os.environ.get("GEMINI_SEARCH_LOCATION", "us-central1")
GEMINI_SEARCH_MODEL = os.environ.get("GEMINI_SEARCH_MODEL", "gemini-2.5-flash")
GEMINI_SEARCH_TEMPERATURE = float(os.environ.get("GEMINI_SEARCH_TEMPERATURE", "0.7"))
GEMINI_SEARCH_MAX_OUTPUT_TOKENS = int(os.environ.get("GEMINI_SEARCH_MAX_OUTPUT_TOKENS", "2000"))

GUIDELINE_DOMAINS = (
    "acep.org",
    "ahajournals.org",
    "heart.org",
    "stroke.org",
    "sccm.org",
    "neurocriticalcare.org",
    "asra.com",
    "resus.org.uk",
    "guidelinecentral.com",
    "acepnow.com",
)

PREFERRED_EM_JOURNAL_PATTERNS = (
    "western journal of emergency medicine",
    "westjem",
    "jacep open",
    "journal of the american college of emergency physicians open",
    "american journal of emergency medicine",
    "annals of emergency medicine",
    "academic emergency medicine",
    "acad emerg med",
    "journal of emergency medicine",
    "pediatric emergency care",
    "advanced journal of emergency medicine",
    "prehospital emergency care",
    "european journal of emergency medicine",
    "eur j emerg med",
    "air medical journal",
)

PREFERRED_EM_JOURNAL_DOMAINS = (
    "westjem.com",
    "ajemjournal.com",
    "annemergmed.com",
)

PMC_DOMAINS = (
    "ncbi.nlm.nih.gov",
    "pubmed.ncbi.nlm.nih.gov",
    "pmc.ncbi.nlm.nih.gov",
)

PREFERRED_FOAM_DOMAINS = (
    "wikem.org",
    "litfl.com",
    "rebelem.com",
    "aliem.com",
    "emcrit.org",
)

DRUG_REFERENCE_DOMAINS = (
    "drugs.com",
    "medscape.com",
    "epocrates.com",
    "globalrph.com",
)

GRADE_PRIORITY = {
    "guideline": 0,
    "em_journal": 1,
    "pmc": 2,
    "preferred_foam": 3,
    "drug_reference": 4,
    "general_reference": 5,
}

GRADE_LABELS = {
    "guideline": "Guideline",
    "em_journal": "EM Journal",
    "pmc": "PubMed / PMC",
    "preferred_foam": "Preferred FOAM",
    "drug_reference": "Drug Reference",
    "general_reference": "Web Reference",
}


class GeminiSearchService:
    """Stream grounded Gemini Search answers with web citations."""

    def __init__(self):
        self.project_id = PROJECT_ID
        self.location = GEMINI_SEARCH_LOCATION
        self.model = GEMINI_SEARCH_MODEL
        self.temperature = GEMINI_SEARCH_TEMPERATURE
        self.max_output_tokens = GEMINI_SEARCH_MAX_OUTPUT_TOKENS
        self._resolved_uri_cache: Dict[str, str] = {}

    def _get_access_token(self) -> str:
        credentials, _ = google.auth.default()
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        return credentials.token

    def _build_prompt(self, query: str) -> str:
        return f"""You are an emergency medicine clinical assistant for bedside use.

Answer the user's question directly and concisely.

RESPONSE RULES:
- Start with **Bottom Line:** in 1-2 sentences.
- Use markdown tables for medication dosing, contraindications, scoring systems, and comparisons when useful.
- Medication dosing must use standard form: Drug | Dose | Route | Frequency or rate | Max dose | Key cautions.
- Prefer society guidelines and PubMed or PubMed Central sources when available.
- FOAM or blog sources may be used only when clearly relevant and attributed with a URL.
- Never invent citations, URLs, journal names, article titles, authors, DOIs, or PMIDs.
- Include a PMID only when it is explicitly present in the grounded source.
- If a point cannot be supported by grounded sources, say so plainly.
- Be practical and concise for bedside use.

QUESTION: {query}
"""

    def _build_payload(self, query: str) -> Dict:
        return {
            "contents": [{"role": "user", "parts": [{"text": self._build_prompt(query)}]}],
            "tools": [{"googleSearch": {}}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_output_tokens,
            },
        }

    def _extract_text(self, payload: Dict) -> List[str]:
        texts: List[str] = []
        for candidate in payload.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                text = part.get("text", "")
                if text:
                    texts.append(text)
        return texts

    def _extract_grounding_metadata(self, payload: Dict) -> Optional[Dict]:
        for candidate in payload.get("candidates", []):
            metadata = candidate.get("groundingMetadata") or candidate.get("grounding_metadata")
            if metadata:
                return metadata
        return None

    def _label_for_uri(self, uri: str, title: str) -> str:
        if title:
            return title
        parsed = urlparse(uri)
        return parsed.netloc or uri

    def _normalized_domain(self, uri: str) -> str:
        domain = urlparse(uri).netloc.lower()
        if domain.startswith("www."):
            return domain[4:]
        return domain

    def _matches_domain(self, domain: str, known_domains: tuple[str, ...]) -> bool:
        return any(domain == known or domain.endswith(f".{known}") for known in known_domains)

    def _resolve_redirect_url(self, uri: str) -> str:
        if "vertexaisearch.cloud.google.com/grounding-api-redirect" not in uri:
            return uri
        if uri in self._resolved_uri_cache:
            return self._resolved_uri_cache[uri]

        resolved_uri = uri
        try:
            response = requests.get(
                uri,
                allow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=5,
                stream=True,
            )
            resolved_uri = response.url or uri
            response.close()
        except requests.RequestException:
            resolved_uri = uri

        self._resolved_uri_cache[uri] = resolved_uri
        return resolved_uri

    def _infer_source_grade(self, uri: str, title: str) -> str:
        domain = self._normalized_domain(uri)
        title_text = (title or "").lower()
        uri_text = uri.lower()
        combined_text = f"{title_text} {uri_text}"

        if self._matches_domain(domain, GUIDELINE_DOMAINS):
            return "guideline"

        if (
            self._matches_domain(domain, PREFERRED_EM_JOURNAL_DOMAINS)
            or any(pattern in combined_text for pattern in PREFERRED_EM_JOURNAL_PATTERNS)
        ):
            return "em_journal"

        if self._matches_domain(domain, PMC_DOMAINS):
            return "pmc"

        if self._matches_domain(domain, PREFERRED_FOAM_DOMAINS):
            return "preferred_foam"

        if self._matches_domain(domain, DRUG_REFERENCE_DOMAINS):
            return "drug_reference"

        return "general_reference"

    def _build_web_citation(self, uri: str, title: str) -> Dict:
        normalized_uri = self._resolve_redirect_url(uri)
        normalized_domain = self._normalized_domain(normalized_uri)
        source_grade = self._infer_source_grade(normalized_uri, title)
        return {
            "protocol_id": self._label_for_uri(normalized_uri, title),
            "source_uri": normalized_uri,
            "relevance_score": 0,
            "source_type": "web",
            "source_grade": source_grade,
            "source_grade_label": GRADE_LABELS[source_grade],
            "source_domain": normalized_domain,
            "is_preferred_em_source": source_grade in {"guideline", "em_journal", "pmc", "preferred_foam"},
        }

    def _extract_citations(self, grounding_metadata: Optional[Dict]) -> List[Dict]:
        if not grounding_metadata:
            return []

        citations: List[Dict] = []
        seen_uris = set()
        for chunk in grounding_metadata.get("groundingChunks", []):
            web = chunk.get("web") or {}
            uri = web.get("uri") or web.get("url")
            if not uri:
                continue
            normalized_uri = self._resolve_redirect_url(uri)
            if normalized_uri in seen_uris:
                continue
            seen_uris.add(normalized_uri)
            title = web.get("title", "")
            citations.append(self._build_web_citation(normalized_uri, title))

        citations.sort(
            key=lambda citation: (
                GRADE_PRIORITY.get(citation.get("source_grade", "general_reference"), 99),
                citation.get("protocol_id", "").lower(),
            )
        )
        return citations

    def _extract_search_entry_point_html(self, grounding_metadata: Optional[Dict]) -> Optional[str]:
        if not grounding_metadata:
            return None
        search_entry_point = grounding_metadata.get("searchEntryPoint", {})
        rendered_content = search_entry_point.get("renderedContent")
        return rendered_content or None

    def _extract_search_queries(self, grounding_metadata: Optional[Dict]) -> List[str]:
        if not grounding_metadata:
            return []
        return grounding_metadata.get("webSearchQueries", [])

    def query_stream(self, query: str) -> Generator[Dict, None, None]:
        start = time.time()
        url = (
            f"https://{self.location}-aiplatform.googleapis.com/v1/projects/"
            f"{self.project_id}/locations/{self.location}/publishers/google/models/"
            f"{self.model}:streamGenerateContent?alt=sse"
        )
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            url,
            headers=headers,
            json=self._build_payload(query),
            stream=True,
            timeout=60,
        )
        if response.status_code != 200:
            raise Exception(f"Gemini grounded search failed: {response.status_code} - {response.text}")

        latest_grounding: Optional[Dict] = None
        for raw_line in response.iter_lines():
            if not raw_line:
                continue
            line = raw_line.decode("utf-8")
            if not line.startswith("data: "):
                continue
            json_str = line[6:]
            if not json_str or json_str == "[DONE]":
                continue
            try:
                parsed = json.loads(json_str)
            except json.JSONDecodeError:
                continue

            payloads = parsed if isinstance(parsed, list) else [parsed]
            for payload in payloads:
                if not isinstance(payload, dict):
                    continue
                grounding_metadata = self._extract_grounding_metadata(payload)
                if grounding_metadata:
                    latest_grounding = grounding_metadata
                for text in self._extract_text(payload):
                    yield {"type": "chunk", "text": text}

        citations = self._extract_citations(latest_grounding)
        yield {
            "type": "done",
            "citations": citations,
            "images": [],
            "query_time_ms": int((time.time() - start) * 1000),
            "grounded": bool(latest_grounding),
            "model": self.model,
            "search_suggestion_html": self._extract_search_entry_point_html(latest_grounding),
            "search_queries": self._extract_search_queries(latest_grounding),
        }
