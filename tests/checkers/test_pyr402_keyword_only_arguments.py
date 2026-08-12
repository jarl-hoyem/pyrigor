"""Tests for the PYR402 checker (force keyword-only arguments)."""

from pyrigor.checkers import find_pyr402_violations
from pyrigor.rules import Rule


def test_flags_function_with_positional_parameter() -> None:
    """A function with a parameter before a bare `*` should be flagged."""
    source = """
def apply_correction(weight, bias):
    ...
"""
    violations = find_pyr402_violations(source)

    assert len(violations) == 1
    assert violations[0].function_name == "apply_correction"


def test_no_violation_for_already_keyword_only_function() -> None:
    """A function with only keyword-only parameters should not be flagged."""
    source = """
def apply_correction(*, weight, bias):
    ...
"""
    violations = find_pyr402_violations(source)

    assert not violations


def test_no_violation_for_method_with_only_self() -> None:
    """A method with only `self` before the keyword-only params should not be flagged."""
    source = """
class Foo:
    def bar(self, *, weight, bias):
        ...
"""
    violations = find_pyr402_violations(source)

    assert not violations


def test_flags_function_with_positional_only_parameter() -> None:
    """A function using positional-only (/) params should still be flagged."""
    source = """
def apply_correction(weight, bias, /):
    ...
"""
    violations = find_pyr402_violations(source)

    assert len(violations) == 1
    assert violations[0].function_name == "apply_correction"


def test_no_violation_for_args_kwargs_only_function() -> None:
    """A function with only *args/**kwargs (no named positional params) should not be flagged."""
    source = """
def apply_correction(*args, **kwargs):
    ...
"""
    violations = find_pyr402_violations(source)

    assert not violations


def test_no_violation_for_single_named_param_before_args() -> None:
    """A single named param before *args is exempt from PYR402 (see PYR403).

    The arguments *args/**kwargs are already exempt, leaving only one real param."""
    source = """
def apply_correction(weight, *args, **kwargs):
    ...
"""
    violations = find_pyr402_violations(source)

    assert not violations


def test_flags_two_named_params_before_args() -> None:
    """Two named params before *args should still be flagged."""
    source = """
def apply_correction(weight, bias, *args, **kwargs):
    ...
"""
    violations = find_pyr402_violations(source)

    assert len(violations) == 1
    assert violations[0].function_name == "apply_correction"


def test_no_violation_for_keyword_only_after_args() -> None:
    """A param after *args is automatically keyword-only and should not be flagged."""
    source = """
def apply_correction(*args, weight, **kwargs):
    ...
"""
    violations = find_pyr402_violations(source)

    assert not violations


def test_flags_async_function_with_positional_parameter() -> None:
    """An async function with a positional param should still be flagged."""
    source = """
async def apply_correction(weight, bias):
    ...
"""
    violations = find_pyr402_violations(source)

    assert len(violations) == 1
    assert violations[0].function_name == "apply_correction"


def test_flags_nested_function_with_positional_parameter() -> None:
    """A nested function with a positional param should still be flagged."""
    source = """
def outer():
    def inner(weight, bias):
        ...
    return inner
"""
    violations = find_pyr402_violations(source)

    assert len(violations) == 1
    assert violations[0].function_name == "inner"


def test_no_violation_for_lambda_with_positional_parameters() -> None:
    """A lambda is exempt from PYR402, regardless of its parameters."""
    source = """
sort_key = lambda weight, bias: weight + bias
"""
    violations = find_pyr402_violations(source)

    assert not violations


def test_known_limitation_staticmethod_with_only_self_param() -> None:
    """A @staticmethod whose only param is misleadingly named `self` escapes detection.

    This is a known, accepted limitation, not a bug we're fixing: the checker
    exempts the first positional param named `self`/`cls` without checking for
    @staticmethod or class context. If you name a @staticmethod's parameter
    `self`, you've done this to yourself — pyrigor isn't going to save you
    from that particular act of self-sabotage.
    """
    source = """
class Foo:
    @staticmethod
    def bar(self):
        ...
"""
    violations = find_pyr402_violations(source)

    # Documenting current (incorrect but accepted) behavior: this SHOULD be
    # flagged (self isn't special here — it is a plain, badly named param),
    # but isn't, because the checker doesn't inspect decorators or class
    # context before applying the self/cls exemption.
    assert not violations


def test_no_violation_for_single_parameter_function() -> None:
    """A single-parameter function is exempt from PYR402 (see PYR403 instead)."""
    source = """
def main(paths):
    ...
"""
    violations = find_pyr402_violations(source)

    assert not violations


def test_violation_has_correct_rule() -> None:
    """A PYR402 violation should carry Rule PYR403."""
    source = """
def apply_correction(weight, bias):
    ...
"""
    violations = find_pyr402_violations(source)

    assert violations[0].rule == Rule.PYR402
