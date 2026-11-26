"""Knowledge base parsing, embeddings, vector store and retrieval. Offline."""

from __future__ import annotations

from pathlib import Path

import pytest

from rag import Retriever, VectorStore, build_index, ingest, load_skills, parse_skill
from rag.embeddings import HashingEmbeddingProvider
from rag.knowledge_base import KnowledgeBaseError
from rag.vector_store import Chunk, IndexMismatchError
from static_analysis import Finding

SKILL_MD = """---
skill_id: item_99_demo
title: Demo principle
source: Test suite
related: [item_07_virtual_destructors, item_13_use_objects_to_manage_resources]
---

## Rule

Do the thing.

## Example

```cpp
## not a heading inside code
int x = 0;
```

## Fix

Do it right.
"""


def finding(skill_id: str, message: str = "msg") -> Finding:
    return Finding(skill_id, "a.cpp", 1, 1, "X", message)


# --- Knowledge base ---------------------------------------------------------


def test_parse_skill_reads_front_matter_and_sections():
    skill = parse_skill(SKILL_MD)
    assert skill.skill_id == "item_99_demo"
    assert skill.related == (
        "item_07_virtual_destructors",
        "item_13_use_objects_to_manage_resources",
    )
    assert list(skill.sections) == ["Rule", "Example", "Fix"]
    assert "## not a heading inside code" in skill.sections["Example"]
    assert skill.text.startswith("# Demo principle")


def test_parse_skill_rejects_missing_front_matter():
    with pytest.raises(KnowledgeBaseError):
        parse_skill("## Rule\nno front matter")


def test_parse_skill_rejects_missing_required_key():
    with pytest.raises(KnowledgeBaseError, match="title"):
        parse_skill("---\nskill_id: x\nsource: y\n---\n## Rule\nz\n")


def test_repository_knowledge_base_matches_registered_detectors():
    from static_analysis import DETECTORS

    skills = load_skills()
    assert set(DETECTORS) <= set(skills), "every detector needs a SKILL.md"
    for skill in skills.values():
        assert {"Rule", "Why it matters", "Fix"} <= set(skill.sections), skill.skill_id


def test_template_folder_is_not_loaded():
    assert not any(s.startswith("item_XX") for s in load_skills())


# --- Embeddings and vector store -------------------------------------------


def test_hashing_embeddings_are_deterministic_and_normalized():
    provider = HashingEmbeddingProvider(dims=64)
    a1, a2 = provider.embed(["unique_ptr owns memory", "unique_ptr owns memory"])
    assert a1 == a2
    assert abs(sum(v * v for v in a1) - 1.0) < 1e-9


def test_similar_text_scores_higher_than_unrelated_text():
    provider = HashingEmbeddingProvider()
    store = VectorStore(provider.name)
    chunks = [
        Chunk("a", "s", "virtual destructor polymorphic base class delete derived"),
        Chunk("b", "s", "const member function returns value without modifying"),
    ]
    store.add(chunks, provider.embed([c.text for c in chunks]))
    (query,) = provider.embed(["missing virtual destructor in base class"])
    (best, _), _ = store.search(query, k=2)
    assert best.skill_id == "a"


def test_store_round_trips_through_json(tmp_path: Path):
    provider = HashingEmbeddingProvider(dims=32)
    store = build_index(provider=provider)
    path = tmp_path / "index.json"
    store.save(path)
    loaded = VectorStore.load(path, provider.name)
    assert loaded.chunks == store.chunks
    assert loaded.vectors == store.vectors


def test_store_refuses_index_from_another_provider(tmp_path: Path):
    path = tmp_path / "index.json"
    VectorStore("hashing-v1").save(path)
    with pytest.raises(IndexMismatchError):
        VectorStore.load(path, "ollama:nomic-embed-text")


def test_ingest_writes_one_chunk_per_section(tmp_path: Path):
    path = tmp_path / "kb.json"
    store = ingest(index_path=path)
    skills = load_skills()
    assert path.exists()
    assert len(store.chunks) == sum(len(s.sections) for s in skills.values())


# --- Retriever --------------------------------------------------------------


def test_retriever_always_returns_the_exact_skill_first():
    retriever = Retriever.from_disk(index_path=Path("/nonexistent/index.json"))
    context = retriever.retrieve(finding("item_13_use_objects_to_manage_resources"), "delete p;")
    assert context.primary is not None
    assert context.primary.skill_id == "item_13_use_objects_to_manage_resources"
    assert context.sources[0] == "item_13_use_objects_to_manage_resources"


def test_related_chunks_never_repeat_the_primary_skill():
    retriever = Retriever.from_disk(index_path=Path("/nonexistent/index.json"))
    context = retriever.retrieve(
        finding("item_07_virtual_destructors", "virtual destructor delete derived memory leak"),
        "delete s;",
    )
    assert all(c.skill_id != "item_07_virtual_destructors" for c, _ in context.related)
    assert len(context.related) <= retriever.related_k


def test_related_chunks_below_min_score_are_dropped():
    retriever = Retriever.from_disk(index_path=Path("/nonexistent/index.json"))
    retriever.min_score = 1.01  # impossible to reach
    context = retriever.retrieve(finding("item_07_virtual_destructors"), "")
    assert context.related == []


def test_unknown_skill_has_no_primary_but_does_not_fail():
    retriever = Retriever.from_disk(index_path=Path("/nonexistent/index.json"))
    assert retriever.retrieve(finding("item_42_unknown"), "").primary is None


def test_stale_index_on_disk_is_rebuilt_in_memory(tmp_path: Path):
    path = tmp_path / "index.json"
    VectorStore("some-old-provider").save(path)
    retriever = Retriever.from_disk(index_path=path)
    assert retriever.store.provider_name == "hashing-v1"
    assert retriever.store.chunks
