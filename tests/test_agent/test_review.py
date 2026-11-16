"""Prompts, providers and the detect -> retrieve -> generate loop.

No real model is called: a fake provider records the prompt, and the HTTP
providers are tested against a patched urlopen.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from agent import Orchestrator, extract_snippet, group_findings
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
from static_analysis import Finding

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


def test_snippet_marks_several_lines_and_spans_between_them():
    lines = [f"l{n}" for n in range(1, 11)]
    snippet = extract_snippet(lines, [3, 6], context=1)
    assert snippet.splitlines() == [
        "   2 | l2",
        ">> 3 | l3",
        "   4 | l4",
        "   5 | l5",
        ">> 6 | l6",
        "   7 | l7",
    ]


def test_prompt_template_loads_and_renders_all_placeholders():
    prompt = load_prompt("review_explainer")
    assert prompt.id == "review_explainer" and prompt.version == 2
    system, user = prompt.render(
        count="2",
        scope="process()",
        location="a.cpp:41-46",
        findings="- line 41 ...",
        snippet="S",
        reference="R",
        related_block="",
    )
    assert "What is wrong" in system
    assert "ONE fix" in system and "Keep its function" in system
    assert "2 finding(s) in process() at a.cpp:41-46" in user


def test_prompt_render_fails_loudly_on_a_missing_placeholder():
    with pytest.raises(KeyError):
        load_prompt("review_explainer").render(skill_id="x")


# --- Orchestrator -----------------------------------------------------------


def f(line: int, symbol: str, skill: str = "item_13_use_objects_to_manage_resources") -> Finding:
    return Finding(skill, "a.cpp", line, 1, symbol, f"msg {line}")


def test_findings_in_the_same_function_are_grouped():
    groups = group_findings([f(46, "process()"), f(36, "destroy()"), f(41, "process()")])
    assert [[x.line for x in g] for g in groups] == [[36], [41, 46]]


def test_findings_far_apart_in_one_function_are_split():
    groups = group_findings([f(10, "big()"), f(20, "big()"), f(80, "big()")])
    assert [[x.line for x in g] for g in groups] == [[10, 20], [80]]


def test_same_symbol_in_different_files_is_not_grouped():
    a, b = f(1, "x()"), Finding("item_13_use_objects_to_manage_resources", "b.cpp", 1, 1, "x()", "m")
    assert len(group_findings([a, b])) == 2


def test_review_sends_one_grounded_prompt_per_group(retriever):
    llm = FakeLLM()
    items = Orchestrator(llm, retriever).review_file(EXAMPLE)

    assert [[x.line for x in i.findings] for i in items] == [[5], [36], [41, 46]]
    assert [i.scope for i in items] == ["Shape", "destroy()", "process()"]
    assert len(llm.calls) == 3
    assert [i.explanation for i in items] == ["explanation #1", "explanation #2", "explanation #3"]

    _, shape_prompt = llm.calls[0]
    assert ">> 5 | class Shape {" in shape_prompt
    assert "Declare destructors virtual in polymorphic base classes" in shape_prompt
    assert items[0].sources[0] == "item_07_virtual_destructors"

    _, process_prompt = llm.calls[2]
    assert "2 finding(s) in process() at" in process_prompt
    assert ">> 41 |" in process_prompt and ">> 46 |" in process_prompt
    assert "line 41 (item_13_use_objects_to_manage_resources)" in process_prompt


def test_prompt_contains_principles_but_no_example_code(retriever):
    llm = FakeLLM()
    Orchestrator(llm, retriever).review_file(EXAMPLE)
    prompts = "\n".join(user for _, user in llm.calls)
    assert "## Why it matters" in prompts and "## Rule" in prompts
    # Generic knowledge-base code that small models copied verbatim:
    for leaked in ("class Plugin", "Parser", "Config", "## Example", "## Fix"):
        assert leaked not in prompts, leaked


def test_sources_list_only_what_the_explanation_used(retriever):
    model_items = Orchestrator(FakeLLM(), retriever).review_file(EXAMPLE)
    for item in model_items:
        assert not any(s.endswith(("#Example", "#Fix")) for s in item.sources), item.sources
    offline_items = Orchestrator(OfflineProvider(), retriever).review_file(EXAMPLE)
    assert [i.sources for i in offline_items] == [
        ["item_07_virtual_destructors"],
        ["item_13_use_objects_to_manage_resources"],
        ["item_13_use_objects_to_manage_resources"],
    ]


def test_offline_provider_explains_from_the_knowledge_base_without_a_model(retriever):
    items = Orchestrator(OfflineProvider(), retriever).review_file(EXAMPLE)
    first = items[0].explanation
    assert first.startswith("Shape declares virtual area()")
    assert "Why it matters:" in first
    assert "class Plugin" not in first  # generic example code is not shown
    process = items[2].explanation
    assert "`new int[samples]` in process()" in process
    assert "Manual `delete[]` in process()" in process


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
    assert "4 finding(s) in 3 group(s)  [provider: offline]" in out
    assert "(sources: item_07_virtual_destructors" in out


def test_cli_review_without_api_key_exits_with_error(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    code = cli_main(["review", str(EXAMPLE), "--provider", "anthropic"])
    assert code == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
