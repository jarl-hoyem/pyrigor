"""Tests for pyrigor.checkers._shared."""

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
