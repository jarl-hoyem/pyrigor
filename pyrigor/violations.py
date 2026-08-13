"""Shared violation type produced by all of pyrigor's checkers."""

import ast
from typing import NamedTuple

from pyrigor.rules import Rule


class Violation(NamedTuple):
    """A single rule violation found by one of pyrigor's checkers."""

    line: int
    column: int
    function_name: str
    rule: Rule


# pyrigor/violations.py
def make_violation(*, node: ast.FunctionDef | ast.AsyncFunctionDef, rule: Rule) -> Violation:
    """Build a Violation from a function node and rule.

    Args:
        node: The function definition the violation was found on.
        rule: Which rule was violated — its problem text is looked up
            automatically, so it can never be mismatched at the call site.

    Returns:
        A populated Violation.
    """
    return Violation(
        line=node.lineno,
        column=node.col_offset + 1,
        function_name=node.name,
        rule=rule,
    )
