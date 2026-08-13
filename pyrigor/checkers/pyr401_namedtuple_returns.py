"""PYR401 checker: flag functions returning a bare multi-value tuple."""

import ast

from pyrigor.rules import Rule
from pyrigor.violations import Violation, make_violation


def _is_bare_multi_value_tuple(*, annotation: ast.expr | None) -> bool:
    """Check whether a return annotation is a bare tuple[...] with 2+ elements.

    Args:
        annotation: The function's return annotation node, or None.

    Returns:
        True if the annotation is tuple[A, B, ...]. And has two or more
        type arguments.
    """
    if not isinstance(annotation, ast.Subscript):
        return False

    if not (isinstance(annotation.value, ast.Name) and annotation.value.id == "tuple"):
        return False

    return isinstance(annotation.slice, ast.Tuple) and len(annotation.slice.elts) >= 2


def find_violations(source: str) -> list[Violation]:
    """Find PYR401 violations in a source string.

    Args:
        source: Python source code to check.

    Returns:
        A list of violations found, one per offending function.
    """
    tree = ast.parse(source)
    violations = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_bare_multi_value_tuple(
            annotation=node.returns
        ):
            violations.append(make_violation(node=node, rule=Rule.PYR401))

    return violations
