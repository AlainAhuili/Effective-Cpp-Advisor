"""Finds the reference material for a finding.

Two steps, on purpose:
1. Exact lookup by ``skill_id``: the detector already knows which principle
   was violated, so the matching SKILL.md is always included. No similarity
   score can make the model explain the wrong rule.
2. Similarity search for supporting sections from *other* skills (e.g. a
   virtual-destructor finding in code that also deletes manually), limited
   to a few chunks above a minimum score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from static_analysis import Finding

from .embeddings import EmbeddingProvider, get_default_provider
from .ingest import DEFAULT_INDEX_PATH, build_index
from .knowledge_base import DEFAULT_SKILLS_DIR, Skill, load_skills
from .vector_store import Chunk, IndexMismatchError, VectorStore


@dataclass
class RetrievedContext:
    primary: Skill | None
    related: list[tuple[Chunk, float]] = field(default_factory=list)

    @property
    def sources(self) -> list[str]:
        names = [self.primary.skill_id] if self.primary else []
        names += [f"{c.skill_id}#{c.section}" for c, _ in self.related]
        return names


class Retriever:
    def __init__(
        self,
        skills: dict[str, Skill],
        store: VectorStore,
        provider: EmbeddingProvider,
        related_k: int = 2,
        min_score: float = 0.15,
    ) -> None:
        self.skills = skills
        self.store = store
        self.provider = provider
        self.related_k = related_k
        self.min_score = min_score

    @classmethod
    def from_disk(
        cls,
        skills_dir: Path = DEFAULT_SKILLS_DIR,
        index_path: Path = DEFAULT_INDEX_PATH,
        provider: EmbeddingProvider | None = None,
    ) -> Retriever:
        """Load the index from ``ingest``; build it in memory if it's missing or stale."""
        provider = provider or get_default_provider()
        try:
            store = VectorStore.load(index_path, provider.name)
        except (FileNotFoundError, IndexMismatchError):
            store = build_index(skills_dir, provider)
        return cls(load_skills(skills_dir), store, provider)

    def retrieve(self, finding: Finding, snippet: str = "") -> RetrievedContext:
        primary = self.skills.get(finding.skill_id)
        related: list[tuple[Chunk, float]] = []
        if self.related_k and self.store.chunks:
            (query,) = self.provider.embed([f"{finding.message}\n{snippet}"])
            hits = self.store.search(query, k=self.related_k, exclude_skill=finding.skill_id)
            related = [(c, s) for c, s in hits if s >= self.min_score]
        return RetrievedContext(primary=primary, related=related)
