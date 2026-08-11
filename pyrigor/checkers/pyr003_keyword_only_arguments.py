"""PYR003 checker: flag functions with parameters before a bare `*`."""

import ast
from typing import NamedTuple


class Violation(NamedTuple):
    """A single PYR003 rule violation."""

    line: int
    function_name: str
    message: str


def _has_violation(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check whether a function definition violates PYR003.

    Args:
        node: The function definition to check.

    Returns:
        True if the function has positional parameters beyond an
        optional leading `self`/`cls`.
    """
    positional_args = list(node.args.posonlyargs) + list(node.args.args)
    if positional_args and positional_args[0].arg in ("self", "cls"):
        positional_args = positional_args[1:]

    return bool(positional_args)


def find_violations(source: str) -> list[Violation]:
    """Find PYR003 violations in a source string.

    PYR003: all parameters should be keyword-only.

    Args:
        source: Python source code to check.

    Returns:
        A list of violations found, one per offending function.
    """
    tree = ast.parse(source)
    violations = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _has_violation(node):
            violations.append(
                Violation(
                    line=node.lineno,
                    function_name=node.name,
                    message=f"Function '{node.name}' has positional parameters; "
                    f"all parameters should be keyword-only (PYR003).",
                )
            )

    return violations
