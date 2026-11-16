"""detect -> retrieve -> generate.

Detection decides *what* is wrong (Clang AST, deterministic). Retrieval picks
the reference material (exact skill match + related sections). The LLM only
explains, grounded in that material. Each step can be tested on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rag import RetrievedContext, Retriever
from static_analysis import Finding, parse_file, run_all

from .llm_provider import LLMProvider, OfflineProvider
from .llm_provider.offline import explain_offline
from .prompts import PromptTemplate, load_prompt

SNIPPET_CONTEXT_LINES = 3


@dataclass
class ReviewItem:
    finding: Finding
    snippet: str
    explanation: str
    sources: list[str]


class Orchestrator:
    def __init__(
        self,
        llm: LLMProvider,
        retriever: Retriever,
        prompt: PromptTemplate | None = None,
    ) -> None:
        self.llm = llm
        self.retriever = retriever
        self.prompt = prompt or load_prompt("review_explainer")

    def review_file(self, path: str | Path, clang_args: list[str] | None = None) -> list[ReviewItem]:
        tu = parse_file(path, clang_args) if clang_args else parse_file(path)
        source_lines = Path(path).read_text(encoding="utf-8").splitlines()
        return [self.review_finding(f, source_lines) for f in run_all(tu)]

    def review_finding(self, finding: Finding, source_lines: list[str]) -> ReviewItem:
        snippet = extract_snippet(source_lines, finding.line)
        context = self.retriever.retrieve(finding, snippet)
        explanation = self._explain(finding, snippet, context)
        return ReviewItem(finding, snippet, explanation.strip(), context.sources)

    def _explain(self, finding: Finding, snippet: str, context: RetrievedContext) -> str:
        if isinstance(self.llm, OfflineProvider):
            sections = context.primary.sections if context.primary else {}
            return explain_offline(finding.message, sections)
        system, user = self.prompt.render(**build_prompt_values(finding, snippet, context))
        return self.llm.complete(system, user)


def extract_snippet(lines: list[str], line: int, context: int = SNIPPET_CONTEXT_LINES) -> str:
    """Lines around ``line`` (1-based), numbered, with the finding's line marked."""
    start = max(1, line - context)
    end = min(len(lines), line + context)
    width = len(str(end))
    out = []
    for n in range(start, end + 1):
        marker = ">>" if n == line else "  "
        out.append(f"{marker} {n:>{width}} | {lines[n - 1]}")
    return "\n".join(out)


def build_prompt_values(finding: Finding, snippet: str, context: RetrievedContext) -> dict[str, str]:
    reference = context.primary.text if context.primary else "(no reference entry for this skill)"
    if context.related:
        related = "\n\n".join(
            f"[{c.skill_id} / {c.section}]\n{c.text}" for c, _ in context.related
        )
        related_block = f"Related reference (use only if relevant):\n{related}"
    else:
        related_block = ""
    return {
        "skill_id": finding.skill_id,
        "location": finding.location(),
        "message": finding.message,
        "snippet": snippet,
        "reference": reference,
        "related_block": related_block,
    }
