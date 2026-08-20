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


def test_context_kind_is_variable_for_ann_assign_node() -> None:
    """make_violation should label an annotated-assignment node's kind as 'Variable', not 'Function'."""
    stmt = ast.parse("x: tuple[int, str] = (1, 'a')").body[0]
    assert isinstance(stmt, ast.AnnAssign)

    violation = make_violation(node=stmt, rule=Rule.PYR301)

    assert violation.context_kind == "Variable"


def test_context_kind_is_call_for_call_node() -> None:
    """make_violation should label a Call node's kind as 'Call', not 'Function'."""
    stmt = ast.parse("compute_total(items)").body[0]
    assert isinstance(stmt, ast.Expr)
    assert isinstance(stmt.value, ast.Call)

    violation = make_violation(node=stmt.value, rule=Rule.PYR406)

    assert violation.context_kind == "Call"


def test_context_kind_is_function_for_function_node() -> None:
    """make_violation should label a function node's kind as 'Function'."""
    stmt = ast.parse("def apply_correction(weight, bias):\n    ...\n").body[0]
    assert isinstance(stmt, ast.FunctionDef)

    violation = make_violation(node=stmt, rule=Rule.PYR402)

    assert violation.context_kind == "Function"
