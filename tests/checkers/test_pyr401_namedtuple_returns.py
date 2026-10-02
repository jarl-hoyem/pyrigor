"""Tests for the PYR401 checker (NamedTuple returns)."""
# test assertions compare against expected literal values by design,
# not a magic-value problem

# noinspection PyProtectedMember
from pyrigor.checkers.pyr401_namedtuple_returns import find_findings
from tests.checker_helpers import check_source


def test_flags_function_with_tuple_return_annotation() -> None:
    """A function annotated to return a plain tuple should be flagged."""
    source = """
def compute_gradient(*, x, y, w, b) -> tuple[float, float]:
    ...
"""
    findings = check_source(source=source, checker=find_findings)

    assert len(findings) == 1
    assert findings[0].message.startswith("Function 'compute_gradient' ")


def test_no_finding_for_unannotated_return() -> None:
    """A function with no return annotation is outside PYR401's scope (see Detection scope in the doc)."""
    source = """
def compute_gradient(*, x, y, w, b):
    ...
"""
    findings = check_source(source=source, checker=find_findings)

    assert not findings


def test_no_finding_for_non_tuple_return() -> None:
    """A function returning a single non-tuple value should not be flagged."""
    source = """
def compute_cost(*, x, y, w, b) -> float:
    ...
"""
    findings = check_source(source=source, checker=find_findings)

    assert not findings


def test_no_finding_for_single_element_tuple_return() -> None:
    """A tuple[X] with only one type argument is not a multi-value return."""
    source = """
def compute_something(*, x) -> tuple[float]:
    ...
"""
    findings = check_source(source=source, checker=find_findings)

    assert not findings


def test_no_finding_for_non_tuple_subscript_return() -> None:
    """A subscripted return type that isn't tuple (for example, dict, list) should not be flagged."""
    source = """
def load_config(*, path) -> dict[str, int]:
    ...
"""
    findings = check_source(source=source, checker=find_findings)

    assert not findings


def test_flags_async_function_with_tuple_return_annotation() -> None:
    """An async function annotated to return a plain tuple should be flagged."""
    source = """
async def compute_gradient(*, x, y, w, b) -> tuple[float, float]:
    ...
"""
    findings = check_source(source=source, checker=find_findings)

    assert len(findings) == 1
    assert findings[0].message.startswith("Function 'compute_gradient' ")
