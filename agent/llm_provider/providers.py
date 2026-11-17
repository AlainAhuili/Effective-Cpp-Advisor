"""Concrete providers. Each reads its model name from an environment variable
so a model upgrade never needs a code change."""

from __future__ import annotations

import os

from .base import LLMError, LLMProvider, post_json


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or os.environ.get("ADVISOR_ANTHROPIC_MODEL", "claude-sonnet-5-5")
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set")

    def complete(self, system: str, prompt: str) -> str:
        data = post_json(
            "https://api.anthropic.com/v1/messages",
            {
                "model": self.model,
                "max_tokens": 1024,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            },
            {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
        )
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or os.environ.get("ADVISOR_OPENAI_MODEL", "gpt-4o-mini")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise LLMError("OPENAI_API_KEY is not set")

    def complete(self, system: str, prompt: str) -> str:
        data = post_json(
            "https://api.openai.com/v1/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
            {"Authorization": f"Bearer {self.api_key}"},
        )
        return data["choices"][0]["message"]["content"]


class OllamaProvider(LLMProvider):
    """Fully local: the model runs in Ollama on this machine."""

    name = "local"

    def __init__(self, model: str | None = None, host: str | None = None) -> None:
        self.model = model or os.environ.get("ADVISOR_OLLAMA_MODEL", "llama3.1")
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")

    def complete(self, system: str, prompt: str) -> str:
        data = post_json(
            f"{self.host}/api/chat",
            {
                "model": self.model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
            {},
        )
        return data["message"]["content"]
