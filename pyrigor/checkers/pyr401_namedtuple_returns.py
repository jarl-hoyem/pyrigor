"""PYR401 checker: flag functions returning a bare multi-value tuple."""

import ast

from pyrigor.checkers._shared import find_function_violations, is_bare_multi_value_tuple, walk_once
from pyrigor.rules import Rule
from pyrigor.violations import Violation


def _has_violation(*, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check whether a function definition violates PYR401.

    Args:
        node: The function definition to check.

    Returns:
        True if the function's return annotation is a bare
        multi-value tuple.
    """
    return is_bare_multi_value_tuple(annotation=node.returns)


def find_violations(*, tree: ast.Module) -> list[Violation]:
    """Find PYR401 violations in a parsed source tree.

    Args:
        tree: The parsed AST of a Python source file.

    Returns:
        A list of violations found, one per offending function.
    """
    nodes = walk_once(tree=tree).function_nodes
    return find_function_violations(nodes=nodes, predicate=_has_violation, rule=Rule.PYR401)
