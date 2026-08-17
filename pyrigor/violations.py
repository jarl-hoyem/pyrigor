"""Shared violation type produced by all of pyrigor's checkers."""

import ast
from typing import NamedTuple

from pyrigor.rules import Rule


class Violation(NamedTuple):
    """A single rule violation found by one of pyrigor's checkers."""

    line: int
    column: int
    context_name: str
    rule: Rule


def _name_from_ann_assign(*, node: ast.AnnAssign) -> str:
    """Extract the assigned name from an annotated-assignment node.

    Args:
        node: The annotated assignment to inspect.

    Returns:
        The target's name, or "<unknown>" for an unsupported target shape.
    """
    if isinstance(node.target, ast.Name):
        return node.target.id
    if isinstance(node.target, ast.Attribute):
        return node.target.attr
    return "<unknown>"


def _name_from_call(*, node: ast.Call) -> str:
    """Extract the callee's name from a call node.

    Args:
        node: The call to inspect.

    Returns:
        The callee's bare name, or "<unknown>" for a non-Name callee.
    """
    return node.func.id if isinstance(node.func, ast.Name) else "<unknown>"


def make_violation(*, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.AnnAssign | ast.Call, rule: Rule) -> Violation:
    """Build a Violation from a function, annotated-assignment, or call-statement node and rule.

    Args:
        node: The node the violation was found on.
        rule: Which rule was violated — its problem text is looked up
            automatically, so it can never be mismatched at the call site.

    Returns:
        A populated Violation.
    """
    if isinstance(node, ast.AnnAssign):
        name = _name_from_ann_assign(node=node)
    elif isinstance(node, ast.Call):
        name = _name_from_call(node=node)
    else:
        name = node.name

    return Violation(
        line=node.lineno,
        column=node.col_offset + 1,
        context_name=name,
        rule=rule,
    )
