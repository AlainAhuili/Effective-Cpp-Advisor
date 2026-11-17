"""The embedding interface the rest of the code depends on."""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Turns text into fixed-length vectors. ``name`` is stored in the index so
    an index built with one provider is never queried with another."""

    name: str

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """One vector per input text, all of the same length."""
