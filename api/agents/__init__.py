"""
Agent platform for EMA.

Importing this package registers all built-in agents in the shared `registry`
(each agent module registers its AgentSpec on import). Products enumerate agents
by tier:

    from agents import registry, Tier
    registry.list(Tier.LITE)      # EM App — the free/lite front door
    registry.list(Tier.PLATFORM)  # EM Agents — full Epic-integrated platform

The product difference is configuration, not duplicated code: which agents a
surface exposes (by tier) and whether AgentContext.patient is populated (Epic).
"""

from .base import AgentContext, AgentSpec, Tier, registry

# Import each agent module for its registration side effect. Keep this list as
# the single place new agents are wired into the platform.
from . import local_protocol  # noqa: F401
from . import protocol_search  # noqa: F401

__all__ = ["AgentContext", "AgentSpec", "Tier", "registry"]
