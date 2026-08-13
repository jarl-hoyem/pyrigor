"""Shared AST helpers used by more than one pyrigor checker."""

import ast
from typing import NamedTuple, Protocol

from pyrigor.rules import Rule
from pyrigor.violations import Violation, make_violation


def is_bare_multi_value_tuple(*, annotation: ast.expr | None) -> bool:
    """Check whether a type annotation is a bare tuple[...] with 2+ elements.

    Args:
        annotation: The annotation to check (a return annotation or a
            parameter annotation), or None.

    Returns:
        True if the annotation is tuple[A, B, ...]. With two or more
        type arguments.
    """
    if not isinstance(annotation, ast.Subscript):
        return False

    if not (isinstance(annotation.value, ast.Name) and annotation.value.id == "tuple"):
        return False

    return isinstance(annotation.slice, ast.Tuple) and len(annotation.slice.elts) >= 2


class _ParameterCounts(NamedTuple):
    """The result of counting a function's parameters, with self/cls stripped."""

    positional_args: list[ast.arg]
    total_params: int


def count_parameters(*, node: ast.FunctionDef | ast.AsyncFunctionDef) -> _ParameterCounts:
    """Count a function's parameters, stripping a leading self/cls if present.

    Args:
        node: The function definition to inspect.

    Returns:
        The stripped positional args, and the total parameter count
        (positional plus keyword-only, after stripping).
    """
    positional_args = list(node.args.posonlyargs) + list(node.args.args)
    if positional_args and positional_args[0].arg in ("self", "cls"):
        positional_args = positional_args[1:]

    total_params = len(positional_args) + len(node.args.kwonlyargs)
    return _ParameterCounts(positional_args=positional_args, total_params=total_params)


class _PredicateFun(Protocol):  # pylint: disable=too-few-public-methods
    """A function checking whether a node violates some rule, called by a keyword."""

    def __call__(self, *, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool: ...


def find_violations_by_predicate(*, tree: ast.Module, predicate: _PredicateFun, rule: Rule) -> list[Violation]:
    """Walk a tree, flagging every function matching a predicate as a violation.

    Args:
        tree: The parsed AST of a Python source file.
        predicate: Returns True for a function that violates the rule.
        rule: Which rule to record the violation against.

    Returns:
        A list of violations found, one per matching function.
    """
    violations = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and predicate(node=node):
            violations.append(make_violation(node=node, rule=rule))

    return violations
