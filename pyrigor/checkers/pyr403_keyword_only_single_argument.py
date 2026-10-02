"""PYR403 checker: flag single-parameter functions with a positional parameter."""

import ast

from pyrigor.checkers._shared import WalkedNodes, count_parameters, find_function_findings
from pyrigor.finding_builder import FindingContext
from pyrigor.findings import Finding
from pyrigor.rules import Rule


def _has_finding(*, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
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


def find_findings(*, nodes: WalkedNodes, context: FindingContext) -> list[Finding]:
    """Find PYR403 findings in already-walked nodes.

    Args:
        nodes: Every relevant node in the file, from walk_once.
        context: Source positions and names used to build findings.

    Returns:
        A list of findings found, one per offending function.
    """
    # noinspection PyTypeChecker
    return find_function_findings(nodes=nodes.function_nodes, predicate=_has_finding, rule=Rule.PYR403, context=context)
