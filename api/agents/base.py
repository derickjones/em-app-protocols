"""
Agent platform — shared context + registry.

EM Agents is a platform of agents; EM App is the free/lite front door that
exposes just the search agent with no Epic patient context. Rather than two
codebases, the product difference is expressed here as configuration:

  • which agents a product exposes  → each agent declares its `tiers`
  • whether it has patient context  → AgentContext.patient is populated (EM
    Agents) or left None (EM App)

Deliberately minimal: this is a CATALOG + a shared input contract, NOT a heavy
framework. Both agents "plug in the same way" by registering an AgentSpec. We do
NOT force a uniform run()/execute() contract yet — with only two agents whose
execution shapes differ (a streaming search vs. a synchronous relevance judge),
locking an execution interface now would be a premature abstraction. It can
harden once several agents exist to validate it against.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class Tier(str, Enum):
    """Which product surface exposes an agent."""
    LITE = "lite"          # EM App — free/lite front door (browser, no Epic)
    PLATFORM = "platform"  # EM Agents — full Epic-integrated platform


@dataclass
class AgentContext:
    """
    Shared input for agents. This is the concrete expression of the product
    difference: `patient` is populated only on the EM Agents platform (from Epic
    via epic_fhir.fetch_epic_patient_bundle) and stays None for EM App, so the
    same agent code serves both products unchanged.
    """
    query: str
    enterprise_id: Optional[str] = None
    ed_ids: List[str] = field(default_factory=list)
    user_id: Optional[str] = None
    patient: Optional[Dict[str, Any]] = None  # Epic FHIR bundle, or None (EM App)

    @property
    def has_patient_context(self) -> bool:
        return self.patient is not None


@dataclass(frozen=True)
class AgentSpec:
    """
    Catalog entry describing an agent. Metadata only — an agent's execution lives
    in its own module (or, for the search agent today, in rag_service). This is
    what both products enumerate to decide which agents to show.
    """
    id: str
    name: str
    description: str
    tiers: Tuple[Tier, ...]                 # products that expose this agent
    requires_patient_context: bool = False  # true = only useful with Epic data

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tiers": [t.value for t in self.tiers],
            "requires_patient_context": self.requires_patient_context,
        }


class _Registry:
    """In-memory catalog of registered agents."""

    def __init__(self) -> None:
        self._agents: Dict[str, AgentSpec] = {}

    def register(self, spec: AgentSpec) -> AgentSpec:
        if spec.id in self._agents:
            raise ValueError(f"agent id already registered: {spec.id}")
        self._agents[spec.id] = spec
        return spec

    def get(self, agent_id: str) -> Optional[AgentSpec]:
        return self._agents.get(agent_id)

    def list(self, tier: Optional[Tier] = None) -> List[AgentSpec]:
        specs = list(self._agents.values())
        if tier is not None:
            specs = [s for s in specs if tier in s.tiers]
        return specs


# Single process-wide registry. Agents register themselves on import (see
# agents/__init__.py, which imports each agent module for its side effect).
registry = _Registry()
