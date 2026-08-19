"""Tests for pyrigor.checkers._shared."""
# test assertions compare against expected literal values by design,
# not a magic-value problem
# pylint: disable=magic-value-comparison

import ast

# noinspection PyProtectedMember
from pyrigor.checkers._shared import walk_once


def test_walk_once_collects_function_nodes() -> None:
    """walk_once should collect function definitions into their own list."""
    source = """
def compute() -> int:
    ...
"""
    result = walk_once(tree=ast.parse(source))

    assert len(result.function_nodes) == 1
    assert result.function_nodes[0].name == "compute"


def test_walk_once_collects_assign_nodes() -> None:
    """walk_once should collect annotated assignments into their own list."""
    source = """
x: int = 5
"""
    result = walk_once(tree=ast.parse(source))

    assert len(result.assign_nodes) == 1

    target = result.assign_nodes[0].target
    assert isinstance(target, ast.Name)
    assert target.id == "x"


def test_walk_once_collects_call_statement_nodes_separately() -> None:
    """walk_once should collect bare call-statement expressions into their own list."""
    source = """
def bad_compute() -> int:
    ...

def good_compute() -> int:
    ...

bad_compute()
result = good_compute()
"""
    result = walk_once(tree=ast.parse(source))

    assert len(result.call_statement_nodes) == 1
    func = result.call_statement_nodes[0].func
    assert isinstance(func, ast.Name)
    assert func.id == "bad_compute"


def test_walk_once_collects_class_nodes() -> None:
    """walk_once should collect class definitions into their own list."""
    source = """
class Example:
    ...
"""
    result = walk_once(tree=ast.parse(source))

    assert len(result.class_nodes) == 1
    assert result.class_nodes[0].name == "Example"


def test_walk_once_class_nodes_is_empty_without_classes() -> None:
    """walk_once should return an empty 'class_nodes' list when the source has no classes."""
    source = """
def compute() -> int:
    ...
"""
    result = walk_once(tree=ast.parse(source))

    assert result.class_nodes == []


def test_walk_once_collects_multiple_class_nodes() -> None:
    """walk_once should collect every top-level class, in source order."""
    source = """
class First:
    ...

class Second:
    ...
"""
    result = walk_once(tree=ast.parse(source))

    assert [c.name for c in result.class_nodes] == ["First", "Second"]


def test_walk_once_collects_nested_class_nodes() -> None:
    """walk_once should collect a nested class too, not just top-level ones."""
    source = """
class Outer:
    class Inner:
        ...
"""
    result = walk_once(tree=ast.parse(source))

    assert [c.name for c in result.class_nodes] == ["Outer", "Inner"]
