"""The result type every detector returns."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    """One rule violation at one place in the source.

    ``skill_id`` links the finding to its knowledge-base entry in
    ``skills/effective_cpp/<skill_id>/SKILL.md``, which the RAG layer
    retrieves to ground the LLM's explanation.
    """

    skill_id: str
    file: str
    line: int
    column: int
    symbol: str
    message: str

    def location(self) -> str:
        return f"{self.file}:{self.line}:{self.column}"
