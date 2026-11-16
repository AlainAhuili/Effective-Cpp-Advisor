"""Embedding providers. The default works offline with no model download."""

from __future__ import annotations

from .base import EmbeddingProvider
from .hashing import HashingEmbeddingProvider


def get_default_provider() -> EmbeddingProvider:
    return HashingEmbeddingProvider()


__all__ = ["EmbeddingProvider", "HashingEmbeddingProvider", "get_default_provider"]
