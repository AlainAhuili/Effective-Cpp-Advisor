"""No model at all: the explanation is assembled from the detector messages and
the retrieved SKILL.md.

Used for CI, demos without API keys, and as a baseline. The detector message
already carries a fix tailored to the code, so only the principle's "Why it
matters" is added; the knowledge base's generic example code is left out
because it doesn't match the user's code.
"""

from __future__ import annotations

from .base import LLMProvider

OFFLINE_SECTIONS = ("Why it matters",)


class OfflineProvider(LLMProvider):
    name = "offline"

    def complete(self, system: str, prompt: str) -> str:  # pragma: no cover - not used
        raise NotImplementedError("the orchestrator calls explain_offline() for this provider")


def explain_offline(messages: list[str], skills_sections: list[dict[str, str]]) -> str:
    parts = list(messages)
    for sections in skills_sections:
        for name in OFFLINE_SECTIONS:
            if name in sections:
                parts.append(f"{name}:\n{sections[name]}")
    return "\n\n".join(parts)
