"""Tests for pyrigor's shared Violation type and make_violation constructor."""

import ast

from pyrigor.rules import Rule
from pyrigor.violations import make_violation


def test_unknown_context_name_for_unrecognized_call_shape() -> None:
    """A Call node whose func is neither a Name nor an Attribute reports "<unknown>"."""
    stmt = ast.parse("(get_func())()").body[0]
    assert isinstance(stmt, ast.Expr)
    assert isinstance(stmt.value, ast.Call)
    call_node = stmt.value

    violation = make_violation(node=call_node, rule=Rule.PYR406)

    assert violation.context_name == "<unknown>"
