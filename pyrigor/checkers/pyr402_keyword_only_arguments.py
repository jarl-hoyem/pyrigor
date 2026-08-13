"""PYR402 checker: flag functions with parameters before a bare `*`."""

import ast

from pyrigor.rules import Rule
from pyrigor.violations import Violation, make_violation


def _has_violation(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check whether a function definition violates PYR402.

    Args:
        node: The function definition to check.

    Returns:
        True if the function has two or more parameters with at least
        one positional (beyond an optional leading self/cls).
        Single-parameter functions are exempt — see PYR403.
    """
    positional_args = list(node.args.posonlyargs) + list(node.args.args)
    if positional_args and positional_args[0].arg in ("self", "cls"):
        positional_args = positional_args[1:]

    total_params = len(positional_args) + len(node.args.kwonlyargs)
    if total_params < 2:
        return False

    return bool(positional_args)


def find_violations(tree: ast.Module) -> list[Violation]:
    """Find PYR402 violations in a parsed source tree.

    Args:
        tree: The parsed AST of a Python source file.

    Returns:
        A list of violations found, one per offending function.
    """
    violations = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _has_violation(node):
            violations.append(make_violation(node=node, rule=Rule.PYR402))

    return violations
