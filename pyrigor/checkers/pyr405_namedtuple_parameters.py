"""PYR405 checker: flag function parameters typed as a bare multi-value tuple."""

import ast

from pyrigor.checkers._shared import WalkedNodes, find_function_findings, is_bare_multi_value_tuple
from pyrigor.finding_builder import FindingContext
from pyrigor.findings import Finding
from pyrigor.rules import Rule


def _has_finding(*, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check whether any parameter's annotation is a bare multi-value tuple.

    Args:
        node: The function definition to check.

    Returns:
        True if any parameter (positional, positional-only, or
        keyword-only) has a bare tuple[...] annotation with 2+ elements.
    """
    all_args = list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs)
    return any(is_bare_multi_value_tuple(annotation=arg.annotation) for arg in all_args)


def find_findings(*, nodes: WalkedNodes, context: FindingContext) -> list[Finding]:
    """Find PYR405 findings in already-walked nodes.

    Args:
        nodes: Every relevant node in the file, from walk_once.
        context: Source positions and names used to build findings.

    Returns:
        A list of findings found, one per offending function.
    """
    # noinspection PyTypeChecker
    return find_function_findings(nodes=nodes.function_nodes, predicate=_has_finding, rule=Rule.PYR405, context=context)
