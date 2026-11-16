"""Effective C++ Item 7: declare destructors virtual in polymorphic base classes.

A class is polymorphic if it has at least one virtual function. If such a
class has a non-virtual public destructor, deleting a derived object through
a base-class pointer is undefined behavior; in practice the derived part is
never destroyed.

What this detector reports
    Only the *root* of the problem: a polymorphic class whose destructor
    isn't virtual and that doesn't inherit polymorphism from a base already
    reported. Derived classes of such a base would repeat the same finding.

What it deliberately accepts
    - a virtual destructor, declared or inherited from a base
    - a protected non-virtual destructor (the base can't be deleted through
      a base pointer by outside code; C++ Core Guidelines C.35)
    - classes marked ``final`` (nothing can derive from them)
"""

from __future__ import annotations

from clang import cindex
from clang.cindex import AccessSpecifier, CursorKind

from ..detector_registry import PatternDetector
from ..finding import Finding
from ..parser import is_in_main_file

CLASS_KINDS = (CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL, CursorKind.CLASS_TEMPLATE)


class VirtualDestructorDetector(PatternDetector):
    skill_id = "item_07_virtual_destructors"

    def detect(self, tu: cindex.TranslationUnit) -> list[Finding]:
        findings: list[Finding] = []
        for cursor in tu.cursor.walk_preorder():
            if cursor.kind not in CLASS_KINDS or not cursor.is_definition():
                continue
            if not is_in_main_file(cursor, tu):
                continue
            finding = self._check_class(cursor, tu)
            if finding is not None:
                findings.append(finding)
        return findings

    def _check_class(self, cls: cindex.Cursor, tu: cindex.TranslationUnit) -> Finding | None:
        virtual_methods = _own_virtual_methods(cls)
        if not virtual_methods:
            return None
        if _is_final(cls) or _has_virtual_destructor(cls):
            return None
        # Inherited polymorphism: the base is the root of the problem and is
        # reported (or accepted) on its own.
        if any(_is_polymorphic(base) for base in _base_classes(cls)):
            return None

        dtor = _destructor(cls)
        if dtor is not None and dtor.access_specifier == AccessSpecifier.PROTECTED:
            return None

        name = cls.spelling
        methods = ", ".join(f"{m}()" for m in virtual_methods)
        if dtor is None:
            dtor_text = "has no user-declared destructor, so the implicit one is not virtual"
        else:
            dtor_text = "declares a destructor that is not virtual"
        message = (
            f"{name} declares virtual {methods}, so it is a polymorphic base class, "
            f"but it {dtor_text}. Deleting a derived object through a {name}* is "
            f"undefined behavior and skips the derived destructor. "
            f"Fix: declare `virtual ~{name}() = default;`, or make the destructor "
            f"protected if objects must never be deleted through {name}*."
        )
        return Finding(
            skill_id=self.skill_id,
            file=cls.location.file.name,
            line=cls.location.line,
            column=cls.location.column,
            symbol=name,
            message=message,
        )


def _own_virtual_methods(cls: cindex.Cursor) -> list[str]:
    return [
        c.spelling
        for c in cls.get_children()
        if c.kind == CursorKind.CXX_METHOD and (c.is_virtual_method() or c.is_pure_virtual_method())
    ]


def _destructor(cls: cindex.Cursor) -> cindex.Cursor | None:
    for c in cls.get_children():
        if c.kind == CursorKind.DESTRUCTOR:
            return c
    return None


def _base_classes(cls: cindex.Cursor) -> list[cindex.Cursor]:
    bases = []
    for c in cls.get_children():
        if c.kind != CursorKind.CXX_BASE_SPECIFIER:
            continue
        decl = c.type.get_declaration()
        if decl.kind in CLASS_KINDS:
            definition = decl.get_definition() or decl
            bases.append(definition)
    return bases


def _has_virtual_destructor(cls: cindex.Cursor) -> bool:
    """Declared virtual here, or implicitly virtual because a base's is."""
    dtor = _destructor(cls)
    if dtor is not None and dtor.is_virtual_method():
        return True
    return any(_has_virtual_destructor(base) for base in _base_classes(cls))


def _is_polymorphic(cls: cindex.Cursor) -> bool:
    if _own_virtual_methods(cls):
        return True
    dtor = _destructor(cls)
    if dtor is not None and dtor.is_virtual_method():
        return True
    return any(_is_polymorphic(base) for base in _base_classes(cls))


def _is_final(cls: cindex.Cursor) -> bool:
    return any(c.kind == CursorKind.CXX_FINAL_ATTR for c in cls.get_children())
