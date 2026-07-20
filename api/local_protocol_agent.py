"""
Local Protocol Agent
--------------------
EMA already stores every local ED protocol and retrieves candidates for a query
via vector search. That search is recall-oriented, so it drags in coincidental
matches (e.g. a heated-high-flow protocol surfacing for a chest-pain question).
This agent adds the judgment step: given the clinician's question OR a patient's
chief complaint, it asks Gemini to keep only the protocols a clinician would
actually want for THIS situation, and to say briefly why.

Used by rag_service.protocol_summary_stream in place of the old vector-distance
cutoff. If the LLM call or its output can't be used, the caller falls back to
that cutoff, so protocol suggestions can never break.

The input is just text (a typed question today, a patient's chief complaint from
Epic later), so the same agent serves both without changes. The Gemini call is
injected as `generate` to keep this module decoupled and easy to test.
"""

import json
import re
from typing import Callable, Dict, List


def _build_prompt(query: str, candidates: List[Dict]) -> str:
    """Render the agent prompt: the query + a compact list of candidate protocols."""
    blocks = []
    for c in candidates:
        snippet = " ".join((c.get("text") or "").split())[:600]
        blocks.append(f'- protocol_id: "{c["protocol_id"]}"\n  excerpt: {snippet}')
    catalog = "\n".join(blocks)

    return f"""You are the Local Protocol Agent for an emergency medicine app.

A clinician asked a question, or a patient presented with a chief complaint:
"{query}"

Below are candidate local ED protocols pulled from the department's own library.
Decide which are GENUINELY clinically relevant to suggest for this specific
question / chief complaint. Keep a protocol only if a clinician managing THIS
case would actually want it. Drop tangential or coincidental keyword matches.

Example: for chest pain, keep an ACS / troponin rule-out or a STEMI pathway;
drop an unrelated respiratory or orthopedic protocol even if some words overlap.

Return STRICT JSON only, no prose, no code fences:
{{"relevant": [{{"protocol_id": "<exact id from the list>", "reason": "<=12 words"}}]}}
If none apply, return {{"relevant": []}}.

Candidate protocols:
{catalog}
"""


def _parse_relevant(raw: str) -> List[Dict]:
    """
    Extract the {"relevant": [...]} list from the model's text.
    Raises ValueError / JSONDecodeError if it can't be parsed, so the caller can
    fall back rather than silently treating a parse failure as "none relevant".
    """
    match = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not match:
        raise ValueError("no JSON object in Local Protocol Agent output")
    data = json.loads(match.group(0))
    return [
        item
        for item in data.get("relevant", [])
        if isinstance(item, dict) and item.get("protocol_id")
    ]


def select_relevant_protocols(
    query: str,
    candidates: List[Dict],
    generate: Callable[[str], str],
) -> Dict[str, str]:
    """
    Judge which candidate protocols are relevant to `query`.

    Args:
        query:      the clinician's question or a patient's chief complaint.
        candidates: dicts each with at least {"protocol_id": str, "text": str}
                    (text = a short excerpt used only to judge relevance).
        generate:   callable(prompt) -> model text. Injected (Gemini) so this
                    module has no dependency on the RAG service.

    Returns:
        {protocol_id: reason} for the protocols judged relevant, in the model's
        order. An empty dict means the agent judged none relevant. Exceptions
        from `generate` or from parsing propagate so the caller can fall back.
    """
    if not candidates:
        return {}

    raw = generate(_build_prompt(query, candidates))

    valid_ids = {c["protocol_id"] for c in candidates}
    selected: Dict[str, str] = {}
    for item in _parse_relevant(raw):
        pid = item["protocol_id"]
        # Ignore any id the model invented that wasn't in the candidate list.
        if pid in valid_ids and pid not in selected:
            selected[pid] = (item.get("reason") or "").strip()
    return selected
