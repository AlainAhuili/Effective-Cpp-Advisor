"""A tiny vector store: chunks + vectors in one JSON file, cosine search.

The knowledge base is small (a few hundred sections at most), so brute-force
search in pure Python is instant and needs no database. The file records
which embedding provider built it; querying with a different one is refused.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

INDEX_VERSION = 1


@dataclass(frozen=True)
class Chunk:
    skill_id: str
    section: str
    text: str


class IndexMismatchError(RuntimeError):
    pass


class VectorStore:
    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        self.chunks: list[Chunk] = []
        self.vectors: list[list[float]] = []

    def add(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("one vector per chunk required")
        self.chunks.extend(chunks)
        self.vectors.extend(vectors)

    def search(
        self, query: list[float], k: int = 3, exclude_skill: str | None = None
    ) -> list[tuple[Chunk, float]]:
        scored = [
            (chunk, _cosine(query, vec))
            for chunk, vec in zip(self.chunks, self.vectors, strict=True)
            if chunk.skill_id != exclude_skill
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:k]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": INDEX_VERSION,
            "provider": self.provider_name,
            "chunks": [asdict(c) for c in self.chunks],
            "vectors": self.vectors,
        }
        path.write_text(json.dumps(data), encoding="utf-8")

    @classmethod
    def load(cls, path: Path, expected_provider: str) -> VectorStore:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version") != INDEX_VERSION:
            raise IndexMismatchError(f"{path}: index version {data.get('version')}, run `ingest`")
        if data["provider"] != expected_provider:
            raise IndexMismatchError(
                f"{path} was built with {data['provider']}, not {expected_provider}; run `ingest`"
            )
        store = cls(data["provider"])
        store.add([Chunk(**c) for c in data["chunks"]], data["vectors"])
        return store


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0
