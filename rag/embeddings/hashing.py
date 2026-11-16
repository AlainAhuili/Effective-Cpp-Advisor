"""Offline default: hashed bag-of-words vectors.

No model, no network, fully deterministic. Good enough to rank ~100 knowledge
base sections by word overlap (identifiers like `unique_ptr` matter more than
semantics here). Swap in a neural provider via ``EmbeddingProvider`` when
the knowledge base grows.
"""

from __future__ import annotations

import hashlib
import math
import re

from .base import EmbeddingProvider

_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_STOP = frozenset(
    "a an and are as at be but by for from has have if in into is it its of on or "
    "so that the their then there these this to was what when which while with "
    "you your can not no only".split()
)


class HashingEmbeddingProvider(EmbeddingProvider):
    name = "hashing-v1"

    def __init__(self, dims: int = 512) -> None:
        self.dims = dims

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dims
        for token in _tokens(text):
            digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "little") % self.dims
            sign = 1.0 if digest[4] & 1 else -1.0
            vec[bucket] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm else vec


def _tokens(text: str) -> list[str]:
    out = []
    for raw in _TOKEN.findall(text):
        token = raw.lower()
        if len(token) > 1 and token not in _STOP:
            out.append(token)
    return out
