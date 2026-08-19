"""Tests for pyrigor's shared Violation type and make violation constructor."""
# test assertions compare against expected literal values by design,
# not a magic-value problem
# pylint: disable=magic-value-comparison

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


def test_end_line_reflects_multiline_call_span() -> None:
    """make_violation should capture a Call node's real end_line, not just its starting line."""
    source = "compute_total(\n    items,\n)\n"
    stmt = ast.parse(source).body[0]
    assert isinstance(stmt, ast.Expr)
    assert isinstance(stmt.value, ast.Call)
    call_node = stmt.value

    violation = make_violation(node=call_node, rule=Rule.PYR406)

    assert violation.line == 1
    assert violation.end_line == 3
