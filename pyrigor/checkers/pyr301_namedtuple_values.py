"""PYR301 checker: flag annotated assignments typed as a bare multi-value tuple."""

import ast

from pyrigor.checkers._shared import WalkedNodes, find_assign_findings, is_bare_multi_value_tuple
from pyrigor.finding_builder import FindingContext
from pyrigor.findings import Finding
from pyrigor.rules import Rule


def _has_finding(*, node: ast.AnnAssign) -> bool:
    """Check whether an annotated assignment violates PYR301.

    Args:
        node: The annotated assignment to check.

    Returns:
        True if the annotation is a bare multi-value tuple.
    """
    return is_bare_multi_value_tuple(annotation=node.annotation)


# noinspection PyTypeChecker
def find_findings(*, nodes: WalkedNodes, context: FindingContext) -> list[Finding]:
    """Find PYR301 findings in already-walked nodes.

    Args:
        nodes: Every relevant node in the file, from walk_once.
        context: Source positions and names used to build findings.

    Returns:
        A list of findings found, one per offending assignment.
    """
    return find_assign_findings(nodes=nodes.assign_nodes, predicate=_has_finding, rule=Rule.PYR301, context=context)
