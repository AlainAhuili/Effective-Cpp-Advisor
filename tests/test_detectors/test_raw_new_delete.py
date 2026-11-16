"""Tests for Item 13 (use objects to manage resources). No LLM, no network.

The code under test includes a tiny in-memory stand-in for <memory> and <new>,
so the tests don't depend on a C++ standard library being installed.
"""

from __future__ import annotations

import pytest

from static_analysis import DETECTORS, parse_source
from static_analysis.pattern_detectors.raw_new_delete import RawNewDeleteDetector

STD_STUB = """
namespace std {
template <class T> class unique_ptr {
public:
    explicit unique_ptr(T* p);
    void reset(T* p);
};
template <class T> class unique_ptr<T[]> {
public:
    explicit unique_ptr(T* p);
};
template <class T> class shared_ptr {
public:
    explicit shared_ptr(T* p);
};
struct nothrow_t {};
extern const nothrow_t nothrow;
}
void* operator new(decltype(sizeof 0), void* where) noexcept;
void* operator new(decltype(sizeof 0), const std::nothrow_t&) noexcept;
struct Widget { Widget(); };
"""


def findings_for(body: str):
    code = '#include "std_stub.h"\n' + body
    tu = parse_source(code, extra_files={"std_stub.h": STD_STUB})
    assert not list(tu.diagnostics), [str(d) for d in tu.diagnostics]
    return RawNewDeleteDetector().detect(tu)


# --- Violations -------------------------------------------------------------


def test_new_into_raw_pointer_is_reported():
    (finding,) = findings_for("void f() { Widget* w = new Widget; (void)w; }")
    assert finding.skill_id == "item_13_use_objects_to_manage_resources"
    assert finding.symbol == "f()"
    assert finding.line == 2
    assert "`new Widget`" in finding.message
    assert "std::make_unique<Widget>" in finding.message


def test_array_new_suggests_vector():
    (finding,) = findings_for("void f(int n) { int* a = new int[n]; (void)a; }")
    assert "`new int[n]`" in finding.message
    assert "std::vector<int>" in finding.message


def test_manual_delete_is_reported():
    (finding,) = findings_for("void release(Widget* w) { delete w; }")
    assert finding.symbol == "release()"
    assert "Manual `delete`" in finding.message


def test_array_delete_is_named_correctly():
    (finding,) = findings_for("void release(int* a) { delete[] a; }")
    assert "Manual `delete[]`" in finding.message


def test_new_and_delete_in_one_function_give_two_findings():
    body = "void f() {\n  Widget* w = new Widget;\n  delete w;\n}"
    findings = findings_for(body)
    assert [f.line for f in findings] == [3, 4]


def test_factory_returning_raw_new_is_reported():
    (finding,) = findings_for("Widget* make() { return new Widget; }")
    assert finding.symbol == "make()"


def test_nothrow_new_still_allocates_and_is_reported():
    (finding,) = findings_for("void f() { Widget* w = new (std::nothrow) Widget; (void)w; }")
    assert "`new (std::nothrow) Widget`" in finding.message


def test_new_in_constructor_initializer_is_reported():
    body = """
    class Buffer {
    public:
        Buffer() : data_(new int[64]) {}
        ~Buffer() { delete[] data_; }
    private:
        int* data_;
    };
    """
    (finding,) = findings_for(body)  # only the new: the delete is in the destructor
    assert finding.symbol == "Buffer::Buffer()"


def test_global_initializer_is_reported():
    (finding,) = findings_for("Widget* g_widget = new Widget;")
    assert finding.symbol == "a global initializer"


def test_new_inside_lambda_is_reported():
    (finding,) = findings_for("auto make = [] { return new Widget; };")
    assert finding.symbol == "a lambda"


def test_outer_smart_pointer_does_not_excuse_new_in_a_nested_statement():
    # The unique_ptr only takes ownership after the lambda has run; inside the
    # lambda the memory sits in a raw pointer, so the search must stop at the
    # statement boundary instead of climbing up to the unique_ptr.
    body = "void f() { std::unique_ptr<Widget> p(([] { Widget* raw = new Widget; return raw; })()); }"
    (finding,) = findings_for(body)
    assert finding.symbol == "a lambda"


# --- Accepted code ----------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        pytest.param("void f() { std::unique_ptr<Widget> p(new Widget); }", id="unique_ptr-ctor"),
        pytest.param("void f() { std::shared_ptr<Widget> p(new Widget); }", id="shared_ptr-ctor"),
        pytest.param(
            "void f() { std::unique_ptr<int[]> a(new int[8]); }",
            id="unique_ptr-array",
        ),
        pytest.param(
            "std::unique_ptr<Widget> make() { return std::unique_ptr<Widget>(new Widget); }",
            id="returned-inside-unique_ptr",
        ),
        pytest.param(
            "void f(std::unique_ptr<Widget>& p) { p.reset(new Widget); }",
            id="reset-with-new",
        ),
        pytest.param(
            "void f(void* buf) { Widget* w = new (buf) Widget; (void)w; }",
            id="placement-new",
        ),
        pytest.param(
            "class Holder { public: ~Holder() { delete w_; } private: Widget* w_; };",
            id="delete-in-destructor",
        ),
        pytest.param(
            "class NoCopy { public: NoCopy(const NoCopy&) = delete; };",
            id="deleted-function",
        ),
    ],
)
def test_accepted(body):
    assert findings_for(body) == []


def test_new_in_included_header_is_not_reported():
    header = "inline Widget* leak() { return new Widget; }"
    code = '#include "std_stub.h"\n#include "lib.h"\nvoid ok() {}\n'
    tu = parse_source(code, extra_files={"std_stub.h": STD_STUB, "lib.h": header})
    assert not list(tu.diagnostics)
    assert "leak" in [c.spelling for c in tu.cursor.get_children()]
    assert RawNewDeleteDetector().detect(tu) == []


def test_detector_is_registered_under_its_skill_id():
    assert isinstance(
        DETECTORS["item_13_use_objects_to_manage_resources"], RawNewDeleteDetector
    )
