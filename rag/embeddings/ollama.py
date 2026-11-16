"""Neural embeddings from a local Ollama server (no data leaves the machine)."""

from __future__ import annotations

import json
import os
import urllib.request

from .base import EmbeddingProvider


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model: str | None = None, host: str | None = None) -> None:
        self.model = model or os.environ.get("ADVISOR_OLLAMA_EMBED_MODEL", "nomic-embed-text")
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.name = f"ollama:{self.model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        body = json.dumps({"model": self.model, "input": texts}).encode()
        request = urllib.request.Request(
            f"{self.host}/api/embed",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read())
        return data["embeddings"]
