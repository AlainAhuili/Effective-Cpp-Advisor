"""Tests for Item 7 (virtual destructors). Pure AST checks, no LLM, no network."""

from __future__ import annotations

import pytest

from static_analysis import DETECTORS, parse_source
from static_analysis.pattern_detectors.virtual_destructor import VirtualDestructorDetector


def findings_for(code: str, **kwargs):
    tu = parse_source(code, **kwargs)
    return VirtualDestructorDetector().detect(tu)


def symbols(code: str, **kwargs) -> list[str]:
    return [f.symbol for f in findings_for(code, **kwargs)]


# --- Violations -------------------------------------------------------------


def test_polymorphic_base_without_destructor_is_reported():
    code = """
    class Shape {
    public:
        virtual double area() const { return 0.0; }
    };
    """
    (finding,) = findings_for(code)
    assert finding.skill_id == "item_07_virtual_destructors"
    assert finding.symbol == "Shape"
    assert finding.line == 2
    assert "implicit one is not virtual" in finding.message
    assert "virtual ~Shape() = default;" in finding.message


def test_public_non_virtual_destructor_is_reported():
    code = """
    class Shape {
    public:
        ~Shape() {}
        virtual double area() const = 0;
    };
    """
    (finding,) = findings_for(code)
    assert "declares a destructor that is not virtual" in finding.message
    assert "area()" in finding.message


def test_struct_counts_like_class():
    code = "struct Base { virtual void run(); };"
    assert symbols(code) == ["Base"]


def test_class_template_is_reported():
    code = """
    template <typename T>
    class Handler {
    public:
        virtual void handle(const T& value) = 0;
    };
    """
    assert symbols(code) == ["Handler"]


def test_only_root_base_is_reported_not_its_derived_classes():
    code = """
    class Shape { public: virtual double area() const = 0; };
    class Circle : public Shape { public: double area() const override { return 3.14; } };
    class Square : public Shape { public: double area() const override { return 1.0; } };
    """
    assert symbols(code) == ["Shape"]


def test_multiple_violations_in_one_file():
    code = """
    class A { public: virtual void f(); };
    class B { public: void g(); };
    class C { public: virtual void h() = 0; };
    """
    assert symbols(code) == ["A", "C"]


# --- Accepted code ----------------------------------------------------------


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            "class Shape { public: virtual ~Shape() {} virtual double area() const = 0; };",
            id="virtual-destructor",
        ),
        pytest.param(
            "class Shape { public: virtual ~Shape() = default; virtual double area() const = 0; };",
            id="defaulted-virtual-destructor",
        ),
        pytest.param(
            "class Point { public: int x() const { return 0; } };",
            id="not-polymorphic",
        ),
        pytest.param(
            """
            class Base { protected: ~Base() = default; public: virtual void f() = 0; };
            """,
            id="protected-non-virtual-destructor",
        ),
        pytest.param(
            "class Leaf final { public: virtual void f() {} };",
            id="final-class",
        ),
        pytest.param(
            """
            class Base { public: virtual ~Base() = default; };
            class Derived : public Base { public: virtual void extra() {} };
            """,
            id="destructor-virtual-through-base",
        ),
    ],
)
def test_accepted(code):
    assert findings_for(code) == []


def test_classes_from_included_headers_are_not_reported():
    header = "class FromHeader { public: virtual void f(); };"
    code = '#include "lib.h"\nclass Mine { public: virtual ~Mine() = default; };\n'
    tu = parse_source(code, extra_files={"lib.h": header})
    # Guard against a vacuous pass: the header must really be part of the AST.
    assert not list(tu.diagnostics)
    assert "FromHeader" in [c.spelling for c in tu.cursor.get_children()]
    assert VirtualDestructorDetector().detect(tu) == []


def test_finding_points_to_the_analyzed_file():
    (finding,) = findings_for("class X { virtual void f(); };", filename="shapes.cpp")
    assert finding.file == "shapes.cpp"
    assert finding.location() == "shapes.cpp:1:7"


def test_detector_is_registered_under_its_skill_id():
    assert isinstance(DETECTORS["item_07_virtual_destructors"], VirtualDestructorDetector)
