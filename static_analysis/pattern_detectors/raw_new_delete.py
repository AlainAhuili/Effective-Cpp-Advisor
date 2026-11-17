"""Effective C++ Item 13: use objects to manage resources.

Memory obtained with a plain ``new`` and released with a manual ``delete``
leaks as soon as an exception or an early ``return`` skips the ``delete``.
Handing the pointer to a resource-managing object (``std::unique_ptr``,
``std::shared_ptr``, a container) at the moment it is created makes the
release automatic (RAII).

What this detector reports
    - every non-placement ``new`` / ``new[]`` whose result is not handed
      directly to a smart pointer (constructor or ``reset()``)
    - every ``delete`` / ``delete[]`` outside a destructor

What it deliberately accepts
    - ``std::unique_ptr<T>(new T)``, ``std::shared_ptr<T>(new T)`` and
      ``p.reset(new T)``: ownership is taken in the same expression
    - placement new (``new (buffer) T``): it constructs into memory owned
      elsewhere and allocates nothing
    - ``delete`` inside a destructor: that is a hand-written RAII class
      releasing what it owns (its ``new`` is still reported where it happens)
    - ``= delete`` on functions, which is not a delete expression

Known limit: a parenthesized type such as ``new (int)`` looks like placement
new at token level and is accepted.
"""

from __future__ import annotations

from clang import cindex
from clang.cindex import CursorKind

from ..detector_registry import PatternDetector
from ..finding import Finding
from ..parser import is_in_main_file

SMART_POINTERS = frozenset({"unique_ptr", "shared_ptr"})

# Climbing stops at these: an expression that reaches them was not handed to
# a smart pointer within its own full-expression.
STATEMENT_BOUNDARIES = frozenset(
    {
        CursorKind.COMPOUND_STMT,
        CursorKind.RETURN_STMT,
        CursorKind.DECL_STMT,
        CursorKind.FUNCTION_DECL,
        CursorKind.CXX_METHOD,
        CursorKind.CONSTRUCTOR,
        CursorKind.DESTRUCTOR,
        CursorKind.FUNCTION_TEMPLATE,
    }
)

FUNCTION_KINDS = frozenset(
    {
        CursorKind.FUNCTION_DECL,
        CursorKind.CXX_METHOD,
        CursorKind.CONSTRUCTOR,
        CursorKind.DESTRUCTOR,
        CursorKind.FUNCTION_TEMPLATE,
        CursorKind.CONVERSION_FUNCTION,
        CursorKind.LAMBDA_EXPR,
    }
)


class RawNewDeleteDetector(PatternDetector):
    skill_id = "item_13_use_objects_to_manage_resources"

    def detect(self, tu: cindex.TranslationUnit) -> list[Finding]:
        findings: list[Finding] = []
        for child in tu.cursor.get_children():
            if is_in_main_file(child, tu):
                self._visit(child, [], tu, findings)
        return findings

    def _visit(self, cursor, ancestors, tu, findings) -> None:
        if cursor.kind == CursorKind.CXX_NEW_EXPR:
            finding = self._check_new(cursor, ancestors)
            if finding:
                findings.append(finding)
        elif cursor.kind == CursorKind.CXX_DELETE_EXPR:
            finding = self._check_delete(cursor, ancestors)
            if finding:
                findings.append(finding)
        ancestors.append(cursor)
        for child in cursor.get_children():
            self._visit(child, ancestors, tu, findings)
        ancestors.pop()

    def _check_new(self, expr, ancestors) -> Finding | None:
        tokens = [t.spelling for t in expr.get_tokens()]
        if _is_placement_new(tokens):
            return None
        if _handed_to_smart_pointer(ancestors):
            return None

        is_array = "[" in tokens
        allocated = _allocated_type(expr)
        where = _enclosing_function_name(ancestors)
        if is_array:
            fix = (
                f"use std::vector<{allocated}> (or std::make_unique<{allocated}[]>(n)) "
                f"so the array is released automatically"
            )
        else:
            fix = (
                f"create it with std::make_unique<{allocated}>(...) "
                f"(or std::make_shared if ownership is shared)"
            )
        message = (
            f"`{_join_tokens(tokens)}` in {where} allocates memory that no object owns. "
            f"If an exception or an early return skips the matching delete, it leaks. "
            f"Fix: {fix}."
        )
        return self._finding(expr, symbol=where, message=message)

    def _check_delete(self, expr, ancestors) -> Finding | None:
        if any(a.kind == CursorKind.DESTRUCTOR for a in ancestors):
            return None
        tokens = [t.spelling for t in expr.get_tokens()]
        where = _enclosing_function_name(ancestors)
        form = "delete[]" if tokens[1:2] == ["["] else "delete"
        message = (
            f"Manual `{form}` in {where}: memory is released by hand, so every "
            f"path through the code (including exceptions) must reach this line "
            f"exactly once. Fix: let a std::unique_ptr or container own the "
            f"memory and remove the {form}."
        )
        return self._finding(expr, symbol=where, message=message)

    def _finding(self, expr, symbol: str, message: str) -> Finding:
        return Finding(
            skill_id=self.skill_id,
            file=expr.location.file.name,
            line=expr.location.line,
            column=expr.location.column,
            symbol=symbol,
            message=message,
        )


def _is_placement_new(tokens: list[str]) -> bool:
    """``new (args) T``: placement form, unless the argument is std::nothrow,
    which still allocates and returns an owning pointer."""
    if tokens[1:2] != ["("]:
        return False
    depth = 0
    for tok in tokens[1:]:
        if tok == "(":
            depth += 1
        elif tok == ")":
            depth -= 1
            if depth == 0:
                break
        elif tok == "nothrow":
            return False
    return True


def _handed_to_smart_pointer(ancestors) -> bool:
    for anc in reversed(ancestors):
        if anc.kind in STATEMENT_BOUNDARIES:
            return False
        if anc.kind == CursorKind.CALL_EXPR:
            ref = anc.referenced
            owner = ref.semantic_parent if ref is not None else None
            if owner is not None and owner.spelling in SMART_POINTERS:
                return True
    return False


def _join_tokens(tokens: list[str]) -> str:
    """Rebuild readable source: `new int[samples]`, `new (std::nothrow) Widget`."""
    out = ""
    for tok in tokens:
        prev = out[-1:] if out else ""
        needs_space = out and (
            (_is_word(prev) and _is_word(tok[0]))
            or out.endswith("new")
            or prev == ")"
            and _is_word(tok[0])
        )
        out += (" " if needs_space else "") + tok
    return out


def _is_word(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _allocated_type(expr) -> str:
    pointee = expr.type.get_pointee()
    return pointee.spelling or "T"


def _enclosing_function_name(ancestors) -> str:
    for anc in reversed(ancestors):
        if anc.kind in FUNCTION_KINDS:
            if anc.kind == CursorKind.LAMBDA_EXPR:
                return "a lambda"
            if anc.kind in (CursorKind.CONSTRUCTOR, CursorKind.DESTRUCTOR, CursorKind.CXX_METHOD):
                return f"{anc.semantic_parent.spelling}::{anc.spelling}()"
            return f"{anc.spelling}()"
    return "a global initializer"
