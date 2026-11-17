"""Retrieval layer: knowledge base -> vector index -> context for a finding."""

from .ingest import DEFAULT_INDEX_PATH, build_index, ingest
from .knowledge_base import DEFAULT_SKILLS_DIR, Skill, load_skills, parse_skill
from .retriever import RetrievedContext, Retriever
from .vector_store import Chunk, VectorStore

__all__ = [
    "DEFAULT_INDEX_PATH",
    "DEFAULT_SKILLS_DIR",
    "Chunk",
    "RetrievedContext",
    "Retriever",
    "Skill",
    "VectorStore",
    "build_index",
    "ingest",
    "load_skills",
    "parse_skill",
]
