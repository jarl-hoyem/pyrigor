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


def make_violation(*, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.AnnAssign, rule: Rule) -> Violation:
    """Build a Violation from a function or annotated-assignment node and rule.

    Args:
        node: The node the violation was found on.
        rule: Which rule was violated — its problem text is looked up
            automatically, so it can never be mismatched at the call site.

    Returns:
        A populated Violation.
    """
    if isinstance(node, ast.AnnAssign):
        if isinstance(node.target, ast.Name):
            name = node.target.id
        elif isinstance(node.target, ast.Attribute):
            name = node.target.attr
        else:
            name = "<unknown>"
    else:
        name = node.name

    return Violation(
        line=node.lineno,
        column=node.col_offset + 1,
        context_name=name,
        rule=rule,
    )
