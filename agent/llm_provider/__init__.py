"""LLM providers behind one interface. Pick one with ``get_provider(name)``."""

from __future__ import annotations

from .base import LLMError, LLMProvider
from .offline import OfflineProvider
from .providers import AnthropicProvider, OllamaProvider, OpenAIProvider

PROVIDERS = {
    "offline": OfflineProvider,
    "local": OllamaProvider,
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
}


def get_provider(name: str) -> LLMProvider:
    try:
        return PROVIDERS[name]()
    except KeyError:
        raise LLMError(f"unknown provider {name!r}; choose one of {', '.join(PROVIDERS)}") from None


__all__ = [
    "PROVIDERS",
    "AnthropicProvider",
    "LLMError",
    "LLMProvider",
    "OfflineProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "get_provider",
]
