"""PYR403 checker: flag single-parameter functions with a positional parameter."""

import ast

from pyrigor.checkers._shared import count_parameters, find_violations_by_predicate
from pyrigor.rules import Rule
from pyrigor.violations import Violation


def _has_violation(*, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check whether a function definition violates PYR403.

    Args:
        node: The function definition to check.

    Returns:
        True if the function has exactly one parameter (beyond an
        optional leading self/cls), and that parameter is positional
        rather than already keyword-only.
    """
    counts = count_parameters(node=node)
    if counts.total_params != 1:
        return False

    return bool(counts.positional_args)


def find_violations(*, tree: ast.Module) -> list[Violation]:
    """Find PYR403 violations in a parsed source tree.

    Args:
        tree: The parsed AST of a Python source file.

    Returns:
        A list of violations found, one per offending function.
    """
    return find_violations_by_predicate(tree=tree, predicate=_has_violation, rule=Rule.PYR403)
