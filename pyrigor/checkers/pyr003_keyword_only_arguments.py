"""PYR003 checker: flag functions with parameters before a bare `*`."""

import ast
from typing import NamedTuple


class Violation(NamedTuple):
    """A single PYR003 rule violation."""

    line: int
    function_name: str
    message: str


def find_violations(source: str) -> list[Violation]:
    """Find PYR003 violations in a source string.

    Args:
        source: Python source code to check.

    Returns:
        A list of violations found, one per offending function.
    """
    tree = ast.parse(source)
    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.args.args:
                violations.append(
                    Violation(
                        line=node.lineno,
                        function_name=node.name,
                        message=f"Function '{node.name}' has positional parameters; "
                                f"all parameters should be keyword-only (PYR003).",
                    )
                )

    return violations
