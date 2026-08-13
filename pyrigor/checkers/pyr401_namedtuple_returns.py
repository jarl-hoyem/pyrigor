"""PYR401 checker: flag functions returning a bare multi-value tuple."""

import ast

from pyrigor.checkers._shared import is_bare_multi_value_tuple
from pyrigor.rules import Rule
from pyrigor.violations import Violation, make_violation


def find_violations(tree: ast.Module) -> list[Violation]:
    """Find PYR401 violations in a parsed source tree.

    Args:
        tree: The parsed AST of a Python source file.

    Returns:
        A list of violations found, one per offending function.
    """
    violations = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and is_bare_multi_value_tuple(
            annotation=node.returns
        ):
            violations.append(make_violation(node=node, rule=Rule.PYR401))

    return violations
