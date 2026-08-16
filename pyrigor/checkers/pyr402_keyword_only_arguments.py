"""PYR402 checker: flag functions with parameters before a bare `*`."""

import ast

from pyrigor.checkers._shared import count_parameters, find_function_violations, walk_once
from pyrigor.rules import Rule
from pyrigor.violations import Violation


def _has_violation(*, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check whether a function definition violates PYR402.

    Args:
        node: The function definition to check.

    Returns:
        True if the function has two or more parameters with at least
        one positional (beyond an optional leading self/cls).
        Single-parameter functions are exempt — see PYR403.
    """
    counts = count_parameters(node=node)
    if counts.total_params < 2:
        return False

    return bool(counts.positional_args)


def find_violations(*, tree: ast.Module) -> list[Violation]:
    """Find PYR402 violations in a parsed source tree.

    Args:
        tree: The parsed AST of a Python source file.

    Returns:
        A list of violations found, one per offending function.
    """
    nodes = walk_once(tree=tree).function_nodes
    return find_function_violations(nodes=nodes, predicate=_has_violation, rule=Rule.PYR402)
