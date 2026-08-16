"""PYR301 checker: flag annotated assignments typed as a bare multi-value tuple."""

import ast

from pyrigor.checkers._shared import find_assign_violations, is_bare_multi_value_tuple, walk_once
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


def find_violations(*, tree: ast.Module) -> list[Violation]:
    """Find PYR301 violations in a parsed source tree.

    Args:
        tree: The parsed AST of a Python source file.

    Returns:
        A list of violations found, one per offending assignment.
    """
    nodes = walk_once(tree=tree).assign_nodes
    return find_assign_violations(nodes=nodes, predicate=_has_violation, rule=Rule.PYR301)
