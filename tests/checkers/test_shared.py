"""Tests for pyrigor.checkers._shared."""

import ast

from pyrigor.checkers._shared import walk_once


def test_walk_once_collects_function_and_assign_nodes_separately() -> None:
    """walk_once should split function defs and annotated assignments into their own lists."""
    source = """
def compute() -> int:
    ...

x: int = 5
"""
    result = walk_once(tree=ast.parse(source))

    assert len(result.function_nodes) == 1
    assert result.function_nodes[0].name == "compute"
    assert len(result.assign_nodes) == 1
    assert result.assign_nodes[0].target.id == "x"
