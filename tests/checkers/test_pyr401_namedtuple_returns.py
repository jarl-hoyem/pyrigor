"""Tests for the PYR401 checker (NamedTuple returns)."""

import ast

from pyrigor.checkers._shared import walk_once
from pyrigor.checkers.pyr401_namedtuple_returns import find_violations


def test_flags_function_with_tuple_return_annotation() -> None:
    """A function annotated to return a plain tuple should be flagged."""
    source = """
def compute_gradient(*, x, y, w, b) -> tuple[float, float]:
    ...
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "compute_gradient"


def test_no_violation_for_unannotated_return() -> None:
    """A function with no return annotation is outside PYR401's scope (see Detection scope in the doc)."""
    source = """
def compute_gradient(*, x, y, w, b):
    ...
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_no_violation_for_non_tuple_return() -> None:
    """A function returning a single non-tuple value should not be flagged."""
    source = """
def compute_cost(*, x, y, w, b) -> float:
    ...
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_no_violation_for_single_element_tuple_return() -> None:
    """A tuple[X] with only one type argument is not a multi-value return."""
    source = """
def compute_something(*, x) -> tuple[float]:
    ...
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_no_violation_for_non_tuple_subscript_return() -> None:
    """A subscripted return type that isn't tuple (for example, dict, list) should not be flagged."""
    source = """
def load_config(*, path) -> dict[str, int]:
    ...
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_flags_async_function_with_tuple_return_annotation() -> None:
    """An async function annotated to return a plain tuple should be flagged."""
    source = """
async def compute_gradient(*, x, y, w, b) -> tuple[float, float]:
    ...
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "compute_gradient"
