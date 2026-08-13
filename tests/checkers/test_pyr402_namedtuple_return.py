"""Tests for the PYR401 checker (NamedTuple returns)."""

from pyrigor.checkers.pyr401_namedtuple_returns import find_pyr401_violations


def test_flags_function_with_tuple_return_annotation() -> None:
    """A function annotated to return a plain tuple should be flagged."""
    source = """
def compute_gradient(*, x, y, w, b) -> tuple[float, float]:
    ...
"""
    violations = find_pyr401_violations(source)

    assert len(violations) == 1
    assert violations[0].function_name == "compute_gradient"
