Effective C++ Advisor
An agentic code review tool for C++ that combines static analysis,
retrieval-augmented generation (RAG), and a model-agnostic LLM
layer to give grounded, principle-based explanations of common C++
design issues — const-correctness, RAII, virtual destructors, implicit
conversions, and more.
Instead of asking an LLM to "review this code" and hoping it notices
the right things, this project separates detection (deterministic
static analysis) from explanation (LLM generation grounded in a
curated knowledge base via RAG). Detection tells you what is wrong
and where, with certainty. RAG + the LLM tell you why it matters
and how to fix it, grounded in reference material instead of the
model's unverified recollection.
```
$ python -m cli.main detect examples/sample_violations.cpp

examples/sample_violations.cpp: 4 finding(s)
------------------------------------------------------------
[item_07_virtual_destructors] examples/sample_violations.cpp:5:7
  -> Shape declares virtual area(), so it is a polymorphic base class, but it
     has no user-declared destructor, so the implicit one is not virtual.
     Deleting a derived object through a Shape* is undefined behavior and
     skips the derived destructor. Fix: declare `virtual ~Shape() = default;`,
     or make the destructor protected if objects must never be deleted
     through Shape*.
[item_13_use_objects_to_manage_resources] examples/sample_violations.cpp:41:19
  -> `new int[samples]` in process() allocates memory that no object owns.
     If an exception or an early return skips the matching delete, it leaks.
     Fix: use std::vector<int> (or std::make_unique<int[]>(n)) so the array
     is released automatically.
...
```

Implementation status

| Layer | Status |
| --- | --- |
| Detection: Clang AST via `libclang` (`static_analysis/`) | Working: Item 7 (virtual destructors), Item 13 (raw `new`/`delete`, RAII) |
| `detect` CLI command (no LLM) | Working |
| Knowledge base (`skills/effective_cpp/`) | Items 7 and 13 written, template in place |
| RAG retrieval (`rag/`) | Working: exact skill lookup + similarity search over a local JSON index; offline hashing embeddings, optional Ollama embeddings |
| LLM providers and prompts (`agent/`) | Working: `offline` (no model), `local` (Ollama), `anthropic`, `openai`; versioned prompt file |
| `review` and `ingest` CLI commands | Working; 63 tests in total, no API key needed |
| MCP tools and closed-loop patch verification | Planned |

The sections below describe the target architecture; parts marked
"Planned" above are not implemented yet.

Architecture
```
parse (static_analysis/) -> detect -> retrieve (rag/) -> generate (agent/)
```
Detection — pattern detectors scan C++ source for known issues
(raw pointer ownership, missing const, missing virtual destructor,
non-explicit single-arg constructors). Each detector maps 1:1 to a
`skill_id`.
Retrieval — the matching `SKILL.md` document (plus related
items) is fetched from a local vector store built from the
`skills/` knowledge base.
Generation — the LLM is prompted with the specific code snippet
and the retrieved reference material, and asked to produce a
grounded, specific explanation — not a generic lecture.
```
effective-cpp-advisor/
├── skills/effective_cpp/       # curated knowledge base (SKILL.md per principle)
├── rag/                        # ingestion, vector store, retrieval
│   └── embeddings/             # embedding provider interface (local/hosted)
├── static_analysis/
│   └── pattern_detectors/      # one detector per detectable principle
├── agent/
│   ├── llm_provider/           # LLM provider interface (Anthropic/OpenAI/local)
│   ├── prompts/                # versioned prompt templates (not hardcoded strings)
│   └── orchestrator.py         # ties detect -> retrieve -> generate together
├── cli/                        # `review` and `ingest` commands
├── examples/                   # sample file with intentional violations
└── tests/test_detectors/       # detector unit tests, no LLM required
```
Setup
```bash
pip install -r requirements.txt

# Detectors only (no LLM)
python -m cli.main detect examples/sample_violations.cpp

# Build the RAG index from skills/effective_cpp/*/SKILL.md (review also builds it on the fly)
python -m cli.main ingest

# Review a file: detect -> retrieve -> explain. Pick a provider:
python -m cli.main review examples/sample_violations.cpp                        # offline: knowledge base only, no model
python -m cli.main review examples/sample_violations.cpp --provider local       # Ollama, fully offline
python -m cli.main review examples/sample_violations.cpp --provider anthropic   # needs ANTHROPIC_API_KEY
python -m cli.main review examples/sample_violations.cpp --provider openai      # needs OPENAI_API_KEY

# Model names come from the environment, so upgrades need no code change:
#   ADVISOR_ANTHROPIC_MODEL, ADVISOR_OPENAI_MODEL, ADVISOR_OLLAMA_MODEL, OLLAMA_HOST
```
Design decisions
Detection is deterministic, not LLM-driven. For a code review tool,
having the LLM decide what to look for is less reliable than
pattern-based static analysis, and it makes detection testable without
a live model call (`tests/test_detectors/` runs with zero API cost).
The LLM's job is explanation, not discovery.
RAG over fine-tuning. The knowledge base is ~20 curated `SKILL.md`
files, each independently editable, versioned, and diffable in a PR.
Fine-tuning a model on this content would be slower to iterate on,
opaque about what the model actually "knows," and tied to one provider.
RAG keeps the knowledge base swappable, inspectable, and provider-agnostic.
Provider abstraction is real, not cosmetic. `LLMProvider` and
`EmbeddingProvider` are the only interfaces the rest of the codebase
depends on. The `local` provider (Ollama) proves this: the full
pipeline runs with zero API keys and zero network calls.
Clang AST detectors, not regular expressions. Each detector implements
`PatternDetector.detect()` (see `static_analysis/detector_registry.py`)
and walks the Clang translation unit via the official `libclang` Python
bindings. That means comments, formatting and macros can't fool it, and
semantic facts are available directly: whether a method is virtual,
which access specifier a destructor has, what a class inherits. Only
declarations in the analyzed file are reported, not those from headers.
Prompts are versioned markdown files, not inline strings. See
`agent/prompts/review_explainer.prompt.md` — this makes prompt changes
reviewable in diffs and separable from orchestration code.
Extending
New detectable principle: add a `skills/effective_cpp/item_XX/SKILL.md`
(use `_template/SKILL.md`), write a detector implementing
`PatternDetector`, register it in `detector_registry.py`, re-run `ingest`.
New LLM backend: implement `LLMProvider`, add a branch in
`get_provider()`.
New embedding backend: implement `EmbeddingProvider`, swap the
return of `get_default_provider()`.
Status
Portfolio project in active development. Detection, retrieval and
generation work end to end and are tested without any API key; the MCP
tool layer and closed-loop patch verification are next (see the
implementation status table at the top).
