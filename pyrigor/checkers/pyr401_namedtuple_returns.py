"""PYR401 checker: flag functions returning a bare multi-value tuple."""

import ast

from pyrigor.checkers._shared import WalkedNodes, find_function_findings, is_bare_multi_value_tuple
from pyrigor.finding_builder import FindingContext
from pyrigor.findings import Finding
from pyrigor.rules import Rule


def _has_finding(*, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check whether a function definition violates PYR401.

    Args:
        node: The function definition to check.

    Returns:
        True if the function's return annotation is a bare
        multi-value tuple.
    """
    return is_bare_multi_value_tuple(annotation=node.returns)


def find_findings(*, nodes: WalkedNodes, context: FindingContext) -> list[Finding]:
    """Find PYR401 findings in already-walked nodes.

    Args:
        nodes: Every relevant node in the file, from walk_once.
        context: Source positions and names used to build findings.

    Returns:
        A list of findings found, one per offending function.
    """
    # noinspection PyTypeChecker
    return find_function_findings(nodes=nodes.function_nodes, predicate=_has_finding, rule=Rule.PYR401, context=context)
