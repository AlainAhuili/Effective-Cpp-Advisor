"""The detector interface and the registry of all detectors.

Every detector maps 1:1 to a ``skill_id`` in the knowledge base. The rest of
the system (RAG, LLM, CLI) only depends on ``PatternDetector`` and
``Finding``, so a detector's internals can change without touching them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from clang import cindex

from .finding import Finding


class PatternDetector(ABC):
    """Detects one Effective C++ principle in a translation unit."""

    skill_id: str

    @abstractmethod
    def detect(self, tu: cindex.TranslationUnit) -> list[Finding]:
        """Return all violations of this principle in the main file of ``tu``."""


def _all_detectors() -> list[PatternDetector]:
    # Imported here to keep the registry free of import cycles.
    from .pattern_detectors.virtual_destructor import VirtualDestructorDetector

    return [VirtualDestructorDetector()]


DETECTORS: dict[str, PatternDetector] = {d.skill_id: d for d in _all_detectors()}


def run_all(tu: cindex.TranslationUnit) -> list[Finding]:
    """Run every registered detector and return findings sorted by position."""
    findings = [f for d in DETECTORS.values() for f in d.detect(tu)]
    return sorted(findings, key=lambda f: (f.file, f.line, f.column, f.skill_id))
