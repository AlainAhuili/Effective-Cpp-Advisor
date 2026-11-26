"""detect -> group -> retrieve -> generate.

Detection decides *what* is wrong (Clang AST, deterministic). Findings in the
same function or class are grouped, so related findings (a `new` and its
`delete`) get one consistent fix instead of contradicting ones. Retrieval
picks the reference material: the matching principle by exact skill id,
plus related sections. The LLM only explains, and it sees principles, not
the knowledge base's example code, so it has nothing unrelated to copy.
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
# Findings further apart than this are explained separately even in one function,
# so the prompt stays small enough for local models.
MAX_GROUP_SPAN_LINES = 40
# What the LLM gets from a SKILL.md. "Example" and "Fix" contain generic code
# (other class and function names) that small models tend to copy verbatim.
PROMPT_SECTIONS = ("Rule", "Why it matters", "When not to apply")


@dataclass
class ReviewItem:
    findings: list[Finding]
    snippet: str
    explanation: str
    sources: list[str]

    @property
    def finding(self) -> Finding:
        """The first finding of the group (by position)."""
        return self.findings[0]

    @property
    def scope(self) -> str:
        return self.findings[0].symbol


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

    def review_file(
        self, path: str | Path, clang_args: list[str] | None = None
    ) -> list[ReviewItem]:
        tu = parse_file(path, clang_args) if clang_args else parse_file(path)
        source_lines = Path(path).read_text(encoding="utf-8").splitlines()
        return [self.review_group(g, source_lines) for g in group_findings(run_all(tu))]

    def review_group(self, findings: list[Finding], source_lines: list[str]) -> ReviewItem:
        lines = [f.line for f in findings]
        snippet = extract_snippet(source_lines, lines)
        contexts = self._retrieve(findings, snippet)
        explanation = self._explain(findings, snippet, contexts)
        sources = _unique(s for c in contexts for s in c.sources)
        return ReviewItem(findings, snippet, explanation.strip(), sources)

    def _retrieve(self, findings: list[Finding], snippet: str) -> list[RetrievedContext]:
        """One context per distinct skill in the group, in order of first appearance.

        Only what the explanation actually uses is kept, so the sources shown to
        the user match the input: related sections limited to PROMPT_SECTIONS
        for a model, none for the offline provider (it uses the primary only).
        """
        first_per_skill: dict[str, Finding] = {}
        for f in findings:
            first_per_skill.setdefault(f.skill_id, f)
        contexts = [self.retriever.retrieve(f, snippet) for f in first_per_skill.values()]
        for c in contexts:
            if isinstance(self.llm, OfflineProvider):
                c.related = []
            else:
                c.related = [
                    (chunk, s) for chunk, s in c.related if chunk.section in PROMPT_SECTIONS
                ]
        return contexts

    def _explain(
        self, findings: list[Finding], snippet: str, contexts: list[RetrievedContext]
    ) -> str:
        if isinstance(self.llm, OfflineProvider):
            sections = [c.primary.sections for c in contexts if c.primary]
            return explain_offline([f.message for f in findings], sections)
        system, user = self.prompt.render(**build_prompt_values(findings, snippet, contexts))
        return self.llm.complete(system, user)


def group_findings(findings: list[Finding]) -> list[list[Finding]]:
    """Group by (file, symbol) and keep groups compact.

    Detectors set ``symbol`` to the enclosing function (e.g. ``process()``) or
    the class, so a `new` and the `delete` that frees it land in one group.
    Findings more than MAX_GROUP_SPAN_LINES apart start a new group.
    """
    by_scope: dict[tuple[str, str], list[Finding]] = {}
    for f in sorted(findings, key=lambda f: (f.file, f.line, f.column)):
        by_scope.setdefault((f.file, f.symbol), []).append(f)

    groups: list[list[Finding]] = []
    for scope_findings in by_scope.values():
        current = [scope_findings[0]]
        for f in scope_findings[1:]:
            if f.line - current[0].line > MAX_GROUP_SPAN_LINES:
                groups.append(current)
                current = [f]
            else:
                current.append(f)
        groups.append(current)
    return sorted(groups, key=lambda g: (g[0].file, g[0].line, g[0].column))


def extract_snippet(
    lines: list[str], marked: int | list[int], context: int = SNIPPET_CONTEXT_LINES
) -> str:
    """Lines around the marked lines (1-based), numbered, marked lines flagged with >>."""
    marked_set = {marked} if isinstance(marked, int) else set(marked)
    start = max(1, min(marked_set) - context)
    end = min(len(lines), max(marked_set) + context)
    width = len(str(end))
    out = []
    for n in range(start, end + 1):
        marker = ">>" if n in marked_set else "  "
        out.append(f"{marker} {n:>{width}} | {lines[n - 1]}")
    return "\n".join(out)


def build_prompt_values(
    findings: list[Finding], snippet: str, contexts: list[RetrievedContext]
) -> dict[str, str]:
    primaries = [c.primary for c in contexts if c.primary]
    reference = (
        "\n\n".join(p.text_for(PROMPT_SECTIONS) for p in primaries)
        or "(no reference entry for these findings)"
    )
    related = [
        (chunk, score)
        for c in contexts
        for chunk, score in c.related
        if chunk.section in PROMPT_SECTIONS  # also filtered in _retrieve; kept as a guard
    ]
    if related:
        body = "\n\n".join(f"[{c.skill_id} / {c.section}]\n{c.text}" for c, _ in related)
        related_block = f"Related reference (use only if relevant):\n{body}"
    else:
        related_block = ""
    lines = sorted({f.line for f in findings})
    location = f"{findings[0].file}:{lines[0]}" + (f"-{lines[-1]}" if len(lines) > 1 else "")
    return {
        "count": str(len(findings)),
        "scope": findings[0].symbol,
        "location": location,
        "findings": "\n".join(f"- line {f.line} ({f.skill_id}): {f.message}" for f in findings),
        "snippet": snippet,
        "reference": reference,
        "related_block": related_block,
    }


def _unique(items) -> list[str]:
    seen: dict[str, None] = {}
    for item in items:
        seen.setdefault(item, None)
    return list(seen)
