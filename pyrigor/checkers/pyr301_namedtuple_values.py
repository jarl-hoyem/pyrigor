"""PYR301 checker: flag annotated assignments typed as a bare multi-value tuple."""

import ast

from pyrigor.checkers._shared import WalkedNodes, find_assign_violations, is_bare_multi_value_tuple
from pyrigor.rules import Rule
from pyrigor.violations import Violation


def _has_violation(*, node: ast.AnnAssign) -> bool:
    """Check whether an annotated assignment violates PYR301.

    Args:
        node: The annotated assignment to check.

    Returns:
        True if the annotation is a bare multi-value tuple.
    """
    return is_bare_multi_value_tuple(annotation=node.annotation)


# noinspection PyTypeChecker
def find_violations(*, nodes: WalkedNodes) -> list[Violation]:
    """Find PYR301 violations in already-walked nodes.

    Args:
        nodes: Every relevant node in the file, from walk_once.

    Returns:
        A list of violations found, one per offending assignment.
    """
    return find_assign_violations(nodes=nodes.assign_nodes, predicate=_has_violation, rule=Rule.PYR301)
