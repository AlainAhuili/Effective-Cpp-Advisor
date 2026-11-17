"""Command-line entry point.

    python -m cli.main detect <file.cpp> [<file.cpp> ...] [-- <clang args>]

``detect`` runs only the deterministic detectors: no LLM, no network. The
``review`` command (detect -> retrieve -> explain) arrives with the RAG and
LLM layers.
"""

from __future__ import annotations

import argparse
import sys

from static_analysis import ParseError, parse_file, run_all
from static_analysis.parser import DEFAULT_ARGS


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
        print("-" * 60)
        for f in findings:
            print(f"[{f.skill_id}] {f.location()}")
            print(f"  -> {f.message}")
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
    ns = parser.parse_args(argv)

    if ns.command == "detect":
        return _detect(ns.files, clang_args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
