"""PYR402 checker: flag functions with parameters before a bare `*`."""

import ast

from pyrigor.checkers._shared import WalkedNodes, count_parameters, find_function_violations
from pyrigor.rules import Rule
from pyrigor.violations import Violation

_MINIMUM_PARAMS_FOR_RULE = 2  # single-parameter functions are exempt, see PYR403


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
    if counts.total_params < _MINIMUM_PARAMS_FOR_RULE:
        return False

    return bool(counts.positional_args)


def find_violations(*, nodes: WalkedNodes) -> list[Violation]:
    """Find PYR402 violations in already-walked nodes.

    Args:
        nodes: Every relevant node in the file, from walk_once.

    Returns:
        A list of violations found, one per offending function.
    """
    # noinspection PyTypeChecker
    return find_function_violations(nodes=nodes.function_nodes, predicate=_has_violation, rule=Rule.PYR402)
