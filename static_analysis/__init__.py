"""Deterministic detection layer: Clang AST in, findings out. No LLM involved."""

from .detector_registry import DETECTORS, PatternDetector, run_all
from .finding import Finding
from .parser import ParseError, parse_file, parse_source

__all__ = [
    "DETECTORS",
    "Finding",
    "ParseError",
    "PatternDetector",
    "parse_file",
    "parse_source",
    "run_all",
]
