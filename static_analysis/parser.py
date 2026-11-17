"""Turns C++ source into a Clang translation unit (a full AST).

Detectors work on the AST, not on raw text, so formatting, comments and
macros can't fool them the way they fool regular expressions.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path

from clang import cindex

DEFAULT_ARGS: tuple[str, ...] = ("-x", "c++", "-std=c++17")


class ParseError(RuntimeError):
    """Raised when Clang can't produce a translation unit at all."""


def parse_file(path: str | Path, args: Sequence[str] = DEFAULT_ARGS) -> cindex.TranslationUnit:
    """Parse a C++ file from disk."""
    return _parse(str(path), list(args), unsaved_files=None)


def parse_source(
    code: str,
    filename: str = "input.cpp",
    args: Sequence[str] = DEFAULT_ARGS,
    extra_files: Mapping[str, str] | None = None,
) -> cindex.TranslationUnit:
    """Parse C++ code held in memory.

    ``extra_files`` maps further in-memory file names (e.g. headers the code
    includes) to their contents. Tests use this to avoid touching the disk.
    """
    unsaved = [(filename, code)]
    # Clang resolves `#include "x.h"` relative to the including file's directory
    # (`./x.h` for a bare file name), so register relative headers under that path.
    base_dir = os.path.dirname(filename) or "."
    for name, content in (extra_files or {}).items():
        path = name if os.path.isabs(name) else os.path.join(base_dir, name)
        unsaved.append((path, content))
    return _parse(filename, list(args), unsaved_files=unsaved)


def _parse(filename: str, args: list[str], unsaved_files) -> cindex.TranslationUnit:
    index = cindex.Index.create()
    try:
        return index.parse(filename, args=args, unsaved_files=unsaved_files)
    except cindex.TranslationUnitLoadError as exc:
        raise ParseError(f"Clang could not parse {filename}: {exc}") from exc


def is_in_main_file(cursor: cindex.Cursor, tu: cindex.TranslationUnit) -> bool:
    """True if the cursor is declared in the file being analyzed, not in a header."""
    loc_file = cursor.location.file
    return loc_file is not None and loc_file.name == tu.spelling
