"""Agent runtime package for S.S.O. workflows.

Provides base agent classes and concrete implementations
for Southern Shade workflows defined in SOUTHERN_SHADE_ONBOARDING.md.
"""

from app.agents.base_agent import BaseAgent
from app.agents.sourcing_agent import SourcingAgent

__all__ = ["BaseAgent", "SourcingAgent"]
