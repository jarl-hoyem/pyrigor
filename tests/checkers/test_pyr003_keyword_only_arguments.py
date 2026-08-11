"""Tests for the PYR003 checker (force keyword-only arguments)."""

from pyrigor.checkers import find_pyr003_violations


def test_flags_function_with_positional_parameter() -> None:
    """A function with a parameter before a bare `*` should be flagged."""
    source = """
def apply_correction(weight, bias):
    ...
"""
    violations = find_pyr003_violations(source)

    assert len(violations) == 1
    assert violations[0].function_name == "apply_correction"


def test_no_violation_for_already_keyword_only_function() -> None:
    """A function with only keyword-only parameters should not be flagged."""
    source = """
def apply_correction(*, weight, bias):
    ...
"""
    violations = find_pyr003_violations(source)

    assert not violations


def test_no_violation_for_method_with_only_self() -> None:
    """A method with only `self` before the keyword-only params should not be flagged."""
    source = """
class Foo:
    def bar(self, *, weight, bias):
        ...
"""
    violations = find_pyr003_violations(source)

    assert not violations


def test_flags_function_with_positional_only_parameter() -> None:
    """A function using positional-only (/) params should still be flagged."""
    source = """
def apply_correction(weight, bias, /):
    ...
"""
    violations = find_pyr003_violations(source)

    assert len(violations) == 1
    assert violations[0].function_name == "apply_correction"


def test_no_violation_for_args_kwargs_only_function() -> None:
    """A function with only *args/**kwargs (no named positional params) should not be flagged."""
    source = """
def apply_correction(*args, **kwargs):
    ...
"""
    violations = find_pyr003_violations(source)

    assert not violations


def test_flags_function_with_named_param_before_args() -> None:
    """A named positional param before *args should still be flagged, even though *args itself is exempt."""
    source = """
def apply_correction(weight, *args, **kwargs):
    ...
"""
    violations = find_pyr003_violations(source)

    assert len(violations) == 1
    assert violations[0].function_name == "apply_correction"


def test_no_violation_for_keyword_only_after_args() -> None:
    """A param after *args is automatically keyword-only and should not be flagged."""
    source = """
def apply_correction(*args, weight, **kwargs):
    ...
"""
    violations = find_pyr003_violations(source)

    assert not violations


def test_flags_async_function_with_positional_parameter() -> None:
    """An async function with a positional param should still be flagged."""
    source = """
async def apply_correction(weight, bias):
    ...
"""
    violations = find_pyr003_violations(source)

    assert len(violations) == 1
    assert violations[0].function_name == "apply_correction"
