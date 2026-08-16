"""PYR405 checker: flag function parameters typed as a bare multi-value tuple."""

import ast

from pyrigor.checkers._shared import find_function_violations, is_bare_multi_value_tuple, walk_once
from pyrigor.rules import Rule
from pyrigor.violations import Violation


def _has_violation(*, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check whether any parameter's annotation is a bare multi-value tuple.

    Args:
        node: The function definition to check.

    Returns:
        True if any parameter (positional, positional-only, or
        keyword-only) has a bare tuple[...] annotation with 2+ elements.
    """
    all_args = list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs)
    return any(is_bare_multi_value_tuple(annotation=arg.annotation) for arg in all_args)


def find_violations(*, tree: ast.Module) -> list[Violation]:
    """Find PYR405 violations in a parsed source tree.

    Args:
        tree: The parsed AST of a Python source file.

    Returns:
        A list of violations found, one per offending function.
    """
    nodes = walk_once(tree=tree).function_nodes
    return find_function_violations(nodes=nodes, predicate=_has_violation, rule=Rule.PYR405)
