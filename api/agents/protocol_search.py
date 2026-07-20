"""
EM App Search Agent — catalog entry.

This is the AI search across local protocols, EM references, literature, and
personal files. It *is* the EM App product (the free/lite front door), and it's
also the platform's general search agent.

Its execution currently lives in rag_service.query_stream (a streaming SSE
response), so this module only registers the catalog entry — both products
enumerate it the same way via the registry. When the agent execution interface
firms up, the streaming call can move behind a common runner; there's no need to
refactor that today.
"""

from .base import AgentSpec, Tier, registry

SPEC = registry.register(
    AgentSpec(
        id="protocol_search",
        name="EM App Search",
        description=(
            "AI search across local ED protocols, EM references, peer-reviewed "
            "literature, and the user's own uploaded files."
        ),
        tiers=(Tier.LITE, Tier.PLATFORM),
        requires_patient_context=False,
    )
)
