"""Tests for the PYR403 checker (keyword-only single argument)."""

import ast

# noinspection PyProtectedMember
from pyrigor.checkers._shared import walk_once
from pyrigor.checkers.pyr403_keyword_only_single_argument import find_violations


def test_flags_single_positional_parameter() -> None:
    """A function with exactly one positional parameter should be flagged."""
    source = """
def load_config(path):
    ...
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "load_config"


def test_no_violation_for_already_keyword_only_single_parameter() -> None:
    """A single parameter that is already keyword-only should not be flagged."""
    source = """
def load_config(*, path):
    ...
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_no_violation_for_two_parameters() -> None:
    """A function with two parameters is not PYR403's territory. It belongs to PYR402."""
    source = """
def compute(a, b):
    ...
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_flags_method_with_self_and_one_positional_parameter() -> None:
    """A method with self plus one real positional parameter should be flagged, on the real parameter."""
    source = """
class Loader:
    def load(self, path):
        ...
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "load"


def test_no_violation_for_zero_parameters() -> None:
    """A function with no parameters at all should not be flagged."""
    source = """
def run() -> None:
    ...
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_flags_async_function_with_single_positional_parameter() -> None:
    """An async function with exactly one positional parameter should be flagged."""
    source = """
async def load_config(path):
    ...
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "load_config"
