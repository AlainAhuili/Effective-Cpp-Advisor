"""Prompts, providers and the detect -> retrieve -> generate loop.

No real model is called: a fake provider records the prompt, and the HTTP
providers are tested against a patched urlopen.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from agent import Orchestrator, extract_snippet
from agent.llm_provider import (
    AnthropicProvider,
    LLMError,
    LLMProvider,
    OfflineProvider,
    OllamaProvider,
    OpenAIProvider,
    get_provider,
)
from agent.prompts import load_prompt
from cli.main import main as cli_main
from rag import Retriever

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "sample_violations.cpp"


class FakeLLM(LLMProvider):
    name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, prompt: str) -> str:
        self.calls.append((system, prompt))
        return f"explanation #{len(self.calls)}"


@pytest.fixture(scope="module")
def retriever() -> Retriever:
    return Retriever.from_disk(index_path=Path("/nonexistent/index.json"))


# --- Snippets and prompts ---------------------------------------------------


def test_snippet_marks_the_finding_line_and_clips_at_file_edges():
    lines = ["a", "b", "c", "d"]
    snippet = extract_snippet(lines, 1, context=2)
    assert snippet.splitlines() == [">> 1 | a", "   2 | b", "   3 | c"]


def test_prompt_template_loads_and_renders_all_placeholders():
    prompt = load_prompt("review_explainer")
    assert prompt.id == "review_explainer" and prompt.version == 1
    system, user = prompt.render(
        skill_id="item_x", location="a.cpp:1:1", message="M", snippet="S", reference="R", related_block=""
    )
    assert "What is wrong" in system
    assert "item_x" in user and "a.cpp:1:1" in user and "R" in user


def test_prompt_render_fails_loudly_on_a_missing_placeholder():
    with pytest.raises(KeyError):
        load_prompt("review_explainer").render(skill_id="x")


# --- Orchestrator -----------------------------------------------------------


def test_review_sends_grounded_prompt_per_finding(retriever):
    llm = FakeLLM()
    items = Orchestrator(llm, retriever).review_file(EXAMPLE)

    assert [i.finding.skill_id for i in items] == [
        "item_07_virtual_destructors",
        "item_13_use_objects_to_manage_resources",
        "item_13_use_objects_to_manage_resources",
        "item_13_use_objects_to_manage_resources",
    ]
    assert len(llm.calls) == 4
    assert [i.explanation for i in items] == [f"explanation #{n}" for n in range(1, 5)]

    _, first_prompt = llm.calls[0]
    assert ">> 5 | class Shape {" in first_prompt
    assert "Declare destructors virtual in polymorphic base classes" in first_prompt  # SKILL.md title
    assert items[0].sources[0] == "item_07_virtual_destructors"


def test_offline_provider_explains_from_the_knowledge_base_without_a_model(retriever):
    items = Orchestrator(OfflineProvider(), retriever).review_file(EXAMPLE)
    first = items[0].explanation
    assert first.startswith("Shape declares virtual area()")
    assert "Why it matters:" in first
    assert "virtual ~Shape() = default;" in first


# --- Providers (HTTP mocked) ------------------------------------------------


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def capture_post(monkeypatch, reply: dict) -> list:
    sent = []

    def fake_urlopen(request, timeout):
        sent.append(request)
        return FakeResponse(json.dumps(reply).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return sent


def test_anthropic_request_and_response(monkeypatch):
    sent = capture_post(monkeypatch, {"content": [{"type": "text", "text": "hello"}]})
    out = AnthropicProvider(model="m", api_key="k").complete("SYS", "USER")
    (req,) = sent
    body = json.loads(req.data)
    assert out == "hello"
    assert req.full_url == "https://api.anthropic.com/v1/messages"
    assert req.get_header("X-api-key") == "k"
    assert body["system"] == "SYS" and body["messages"] == [{"role": "user", "content": "USER"}]


def test_openai_request_and_response(monkeypatch):
    sent = capture_post(monkeypatch, {"choices": [{"message": {"content": "hi"}}]})
    out = OpenAIProvider(model="m", api_key="k").complete("SYS", "USER")
    (req,) = sent
    assert out == "hi"
    assert req.get_header("Authorization") == "Bearer k"
    assert json.loads(req.data)["messages"][0] == {"role": "system", "content": "SYS"}


def test_ollama_request_and_response(monkeypatch):
    sent = capture_post(monkeypatch, {"message": {"content": "local"}})
    out = OllamaProvider(model="m", host="http://box:11434/").complete("SYS", "USER")
    (req,) = sent
    assert out == "local"
    assert req.full_url == "http://box:11434/api/chat"
    assert json.loads(req.data)["stream"] is False


def test_missing_api_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
        get_provider("anthropic")


def test_unknown_provider_is_rejected():
    with pytest.raises(LLMError, match="unknown provider"):
        get_provider("gpt-17")


# --- CLI --------------------------------------------------------------------


def test_cli_review_offline_reports_findings(capsys):
    code = cli_main(["review", str(EXAMPLE), "--provider", "offline"])
    out = capsys.readouterr().out
    assert code == 1
    assert "4 finding(s)  [provider: offline]" in out
    assert "(sources: item_07_virtual_destructors" in out


def test_cli_review_without_api_key_exits_with_error(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    code = cli_main(["review", str(EXAMPLE), "--provider", "anthropic"])
    assert code == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
