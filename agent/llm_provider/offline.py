"""No model at all: the explanation is assembled from the retrieved SKILL.md.

Used for CI, demos without API keys, and as a baseline. It shows exactly what
grounding the LLM gets, without the LLM's wording.
"""

from __future__ import annotations

from .base import LLMProvider

# The orchestrator hands this provider the context directly instead of a prompt.
OFFLINE_SECTIONS = ("Why it matters", "Fix")


class OfflineProvider(LLMProvider):
    name = "offline"

    def complete(self, system: str, prompt: str) -> str:  # pragma: no cover - not used
        raise NotImplementedError("the orchestrator calls explain_offline() for this provider")


def explain_offline(finding_message: str, sections: dict[str, str]) -> str:
    parts = [finding_message]
    for name in OFFLINE_SECTIONS:
        if name in sections:
            parts.append(f"{name}:\n{sections[name]}")
    return "\n\n".join(parts)
