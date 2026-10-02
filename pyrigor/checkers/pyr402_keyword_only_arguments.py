"""PYR402 checker: flag functions with parameters before a bare `*`."""

import ast
from typing import Final

from pyrigor.checkers._shared import WalkedNodes, count_parameters, find_function_findings
from pyrigor.finding_builder import FindingContext
from pyrigor.findings import Finding
from pyrigor.rules import Rule

_MINIMUM_PARAMS_FOR_RULE: Final = 2  # single-parameter functions are exempt, see PYR403


def _has_finding(*, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
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


def find_findings(*, nodes: WalkedNodes, context: FindingContext) -> list[Finding]:
    """Find PYR402 findings in already-walked nodes.

    Args:
        nodes: Every relevant node in the file, from walk_once.
        context: Source positions and names used to build findings.

    Returns:
        A list of findings found, one per offending function.
    """
    # noinspection PyTypeChecker
    return find_function_findings(nodes=nodes.function_nodes, predicate=_has_finding, rule=Rule.PYR402, context=context)
