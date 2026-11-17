"""The LLM interface the rest of the code depends on."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod


class LLMError(RuntimeError):
    pass


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def complete(self, system: str, prompt: str) -> str:
        """Return the model's answer to one prompt."""


def post_json(url: str, payload: dict, headers: dict[str, str], timeout: float = 120) -> dict:
    """Small stdlib HTTP helper so providers need no SDK dependency."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise LLMError(f"{url} returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"cannot reach {url}: {exc.reason}") from exc
