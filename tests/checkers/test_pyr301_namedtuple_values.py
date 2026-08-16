"""Tests for the PYR301 checker (NamedTuple values)."""

import ast

from pyrigor.checkers._shared import walk_once
from pyrigor.checkers.pyr301_namedtuple_values import find_violations


def test_flags_variable_with_bare_tuple_annotation() -> None:
    """A variable annotated as a bare multi-value tuple should be flagged."""
    source = """
positions: tuple[int, int] = (3, 7)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "positions"


def test_no_violation_for_non_tuple_annotation() -> None:
    """A variable with an ordinary, non-tuple annotation should not be flagged."""
    source = """
count: int = 5
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_flags_dataclass_field_with_bare_tuple_annotation() -> None:
    """A dataclass field annotated as a bare multi-value tuple should be flagged."""
    source = """
@dataclass
class Robot:
    position: tuple[int, int]
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "position"


def test_no_violation_for_single_element_tuple() -> None:
    """A tuple[X] with only one element is not a multi-value tuple."""
    source = """
wrapper: tuple[int] = (5,)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_flags_attribute_assignment_with_bare_tuple_annotation() -> None:
    """An attribute assignment (for example, self.x) with a bare tuple annotation should be flagged, not skipped."""
    source = """
class Robot:
    def __init__(self) -> None:
        self.position: tuple[int, int] = (0, 0)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "position"


def test_no_crash_on_subscript_assignment_target() -> None:
    """An annotated assignment to a subscript target should not crash."""
    source = """
d["key"]: tuple[int, int] = (0, 0)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "<unknown>"


def test_no_violation_for_non_tuple_subscript_annotation() -> None:
    """A subscripted annotation that isn't tuple (for example, list[int, int]) should not be flagged."""
    source = """
pair: list[int, int] = [1, 2]
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_no_violation_for_unbounded_homogeneous_tuple() -> None:
    """A variable annotated tuple[X, ...] is unbounded and homogeneous, no positional meaning should not be flagged."""
    source = """
values: tuple[int, ...] = (1, 2, 3)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations
