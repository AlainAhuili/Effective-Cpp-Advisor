"""Command-line entry point.

    python -m cli.main detect <file.cpp> ...                 # detectors only, no LLM
    python -m cli.main ingest                                # build the RAG index
    python -m cli.main review <file.cpp> ... --provider P    # detect -> retrieve -> explain

Providers: offline (no model), local (Ollama), anthropic, openai.
Clang arguments go after `--`, e.g. `-- -std=c++20 -Iinclude`.
Exit code: 0 no findings, 1 findings reported, 2 error.
"""

from __future__ import annotations

import argparse
import sys

from static_analysis import ParseError, parse_file, run_all
from static_analysis.parser import DEFAULT_ARGS

RULE = "-" * 60


def _detect(files: list[str], clang_args: list[str]) -> int:
    args = clang_args or list(DEFAULT_ARGS)
    total = 0
    for path in files:
        try:
            tu = parse_file(path, args)
        except ParseError as exc:
            print(exc, file=sys.stderr)
            return 2
        findings = run_all(tu)
        total += len(findings)
        print(f"{path}: {len(findings)} finding(s)")
        print(RULE)
        for f in findings:
            print(f"[{f.skill_id}] {f.location()}")
            print(f"  -> {f.message}")
        print()
    return 1 if total else 0


def _ingest() -> int:
    from rag import DEFAULT_INDEX_PATH, ingest

    store = ingest()
    skills = len({c.skill_id for c in store.chunks})
    print(f"Indexed {len(store.chunks)} sections from {skills} skill(s) with {store.provider_name}")
    print(f"-> {DEFAULT_INDEX_PATH}")
    return 0


def _review(files: list[str], provider_name: str, clang_args: list[str]) -> int:
    from agent import Orchestrator
    from agent.llm_provider import LLMError, get_provider
    from rag import Retriever

    try:
        llm = get_provider(provider_name)
    except LLMError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    orchestrator = Orchestrator(llm, Retriever.from_disk())
    total = 0
    for path in files:
        try:
            items = orchestrator.review_file(path, clang_args or None)
        except (ParseError, LLMError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        count = sum(len(item.findings) for item in items)
        total += count
        print(f"{path}: {count} finding(s) in {len(items)} group(s)  [provider: {provider_name}]")
        print(RULE)
        for item in items:
            for f in item.findings:
                print(f"[{f.skill_id}] {f.location()}")
            print(item.snippet)
            print()
            for line in item.explanation.splitlines():
                print(f"  {line}" if line else "")
            print(f"  (sources: {', '.join(item.sources)})")
            print(RULE)
        print()
    return 1 if total else 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    clang_args: list[str] = []
    if "--" in argv:
        split = argv.index("--")
        argv, clang_args = argv[:split], argv[split + 1 :]

    parser = argparse.ArgumentParser(prog="effective-cpp-advisor")
    sub = parser.add_subparsers(dest="command", required=True)
    detect = sub.add_parser("detect", help="run the static detectors only (no LLM)")
    detect.add_argument("files", nargs="+")
    sub.add_parser("ingest", help="build the RAG index from skills/")
    review = sub.add_parser("review", help="detect, retrieve reference material, explain")
    review.add_argument("files", nargs="+")
    review.add_argument(
        "--provider",
        default="offline",
        choices=["offline", "local", "anthropic", "openai"],
        help="offline: no model (default); local: Ollama; anthropic/openai: API key from env",
    )
    ns = parser.parse_args(argv)

    if ns.command == "detect":
        return _detect(ns.files, clang_args)
    if ns.command == "ingest":
        return _ingest()
    if ns.command == "review":
        return _review(ns.files, ns.provider, clang_args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
