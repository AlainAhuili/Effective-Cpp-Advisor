"""Builds the vector index from the knowledge base: one chunk per section."""

from __future__ import annotations

from pathlib import Path

from .embeddings import EmbeddingProvider, get_default_provider
from .knowledge_base import DEFAULT_SKILLS_DIR, load_skills
from .vector_store import Chunk, VectorStore

DEFAULT_INDEX_PATH = Path(__file__).resolve().parent / "index" / "kb_index.json"


def build_index(
    skills_dir: Path = DEFAULT_SKILLS_DIR,
    provider: EmbeddingProvider | None = None,
) -> VectorStore:
    provider = provider or get_default_provider()
    chunks = []
    for skill in load_skills(skills_dir).values():
        for section, body in skill.sections.items():
            # The title travels with every chunk so a section like "Fix" still
            # says which principle it belongs to.
            chunks.append(Chunk(skill.skill_id, section, f"{skill.title}\n{section}\n{body}"))
    store = VectorStore(provider.name)
    if chunks:
        store.add(chunks, provider.embed([c.text for c in chunks]))
    return store


def ingest(
    skills_dir: Path = DEFAULT_SKILLS_DIR,
    index_path: Path = DEFAULT_INDEX_PATH,
    provider: EmbeddingProvider | None = None,
) -> VectorStore:
    store = build_index(skills_dir, provider)
    store.save(index_path)
    return store
