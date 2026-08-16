"""Tests for the PYR405 checker (NamedTuple parameters)."""

import ast

from pyrigor.checkers._shared import walk_once
from pyrigor.checkers.pyr405_namedtuple_parameters import find_violations


def test_flags_function_with_bare_tuple_parameter() -> None:
    """A function with a parameter typed as a bare multi-value tuple should be flagged."""
    source = """
def step_bot(*, action: tuple[int, int]) -> None:
    ...
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "step_bot"


def test_no_violation_for_normal_parameters() -> None:
    """A function with ordinary, non-tuple parameter types should not be flagged."""
    source = """
def step_bot(*, row: int, col: int) -> None:
    ...
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_flags_positional_only_tuple_parameter() -> None:
    """A positional-only parameter typed as a bare multi-value tuple should still be flagged."""
    source = """
def step_bot(action: tuple[int, int], /) -> None:
    ...
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1


def test_flags_async_function_with_bare_tuple_parameter() -> None:
    """An async function with a bare-tuple parameter should still be flagged."""
    source = """
async def step_bot(*, action: tuple[int, int]) -> None:
    ...
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1


def test_no_violation_for_single_element_tuple_parameter() -> None:
    """A parameter typed as tuple[X] with only one element is not a multi-value tuple."""
    source = """
def wrap_value(*, value: tuple[int]) -> None:
    ...
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_flags_method_with_bare_tuple_parameter_alongside_self() -> None:
    """A method with self (unannotated) plus a bare-tuple parameter should still be flagged, on the real violation."""
    source = """
class Bot:
    def step(self, *, action: tuple[int, int]) -> None:
        ...
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "step"
