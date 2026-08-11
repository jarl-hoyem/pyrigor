"""Tests for the PYR003 checker (force keyword-only arguments)."""

from pyrigor.checkers.pyr003_keyword_only_arguments import find_violations


def test_flags_function_with_positional_parameter() -> None:
    """A function with a parameter before a bare `*` should be flagged."""
    source = """
def apply_correction(weight, bias):
    ...
"""
    violations = find_violations(source)

    assert len(violations) == 1
    assert violations[0].function_name == "apply_correction"


def test_no_violation_for_already_keyword_only_function() -> None:
    """A function with only keyword-only parameters should not be flagged."""
    source = """
def apply_correction(*, weight, bias):
    ...
"""
    violations = find_violations(source)

    assert not violations


def test_no_violation_for_method_with_only_self() -> None:
    """A method with only `self` before the keyword-only params should not be flagged."""
    source = """
class Foo:
    def bar(self, *, weight, bias):
        ...
"""
    violations = find_violations(source)

    assert not violations
