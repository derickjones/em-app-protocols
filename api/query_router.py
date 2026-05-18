"""Deterministic query routing for the Gemini search pilot."""

from typing import Literal

QueryRoute = Literal["local_protocol", "personal", "general_clinical"]

_PERSONAL_PHRASES = (
    "my file",
    "my files",
    "my upload",
    "my uploads",
    "my uploaded",
    "uploaded pdf",
    "uploaded file",
    "uploaded document",
    "my pdf",
    "my document",
    "my documents",
    "my note",
    "my notes",
    "my personal",
    "my material",
    "my materials",
    "my source",
    "my sources",
    "my reference",
    "my references",
    "personal file",
    "personal document",
    "personal materials",
    "personal material",
    "uploaded materials",
    "uploaded notes",
)

_PROTOCOL_TERMS = (
    "protocol",
    "policy",
    "guideline",
    "pathway",
    "order set",
    "orderset",
    "bundle",
    "workflow",
    "algorithm",
)

_LOCAL_CONTEXT_PHRASES = (
    "our ed",
    "our emergency department",
    "what do we do here",
    "how do we do this here",
    "our approach",
    "our local",
    "local protocol",
    "local policy",
    "our protocol",
    "our protocols",
    "our guideline",
    "our guidelines",
    "our pathway",
    "our bundle",
    "our order set",
    "our workflow",
    "hospital protocol",
    "department protocol",
    "selected bundle",
    "selected bundles",
    "mayo",
)


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def route_query(query: str) -> QueryRoute:
    """Route a query to local protocol, personal, or general clinical search."""
    normalized = _normalize(query)
    if not normalized:
        return "general_clinical"

    if any(phrase in normalized for phrase in _PERSONAL_PHRASES):
        return "personal"

    if (
        ("my" in normalized or "uploaded" in normalized or "personal" in normalized)
        and any(
            token in normalized
            for token in (
                "file",
                "pdf",
                "document",
                "note",
                "notes",
                "material",
                "materials",
                "source",
                "sources",
                "reference",
                "references",
            )
        )
    ):
        return "personal"

    if any(
        phrase in normalized
        for phrase in (
            "use my materials",
            "use my personal materials",
            "from my materials",
            "from my personal materials",
            "from my uploaded",
            "in my uploaded",
        )
    ):
        return "personal"

    has_protocol_term = any(term in normalized for term in _PROTOCOL_TERMS)
    has_local_context = any(phrase in normalized for phrase in _LOCAL_CONTEXT_PHRASES)

    if has_protocol_term and has_local_context:
        return "local_protocol"

    if has_protocol_term and any(token in normalized for token in ("our", "local", "mayo", "here")):
        return "local_protocol"

    if any(
        phrase in normalized
        for phrase in (
            "our protocol",
            "our policy",
            "local guideline",
            "local pathway",
            "hospital guideline",
            "department guideline",
            "selected ed",
            "from our protocol",
            "use our protocol",
            "per our protocol",
            "in our bundle",
            "from our bundle",
        )
    ):
        return "local_protocol"

    return "general_clinical"
