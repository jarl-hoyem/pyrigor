"""Shared AST helpers used by more than one pyrigor checker."""

import ast
from typing import Final, NamedTuple, Protocol

from pyrigor.rules import Rule
from pyrigor.violations import Violation, make_violation

_UNBOUNDED_TUPLE_SLICE_LENGTH: Final = 2  # tuple[X, ...] always has exactly [type, Ellipsis]
_MINIMUM_MULTI_VALUE_COUNT: Final = 2  # two or more elements means "multiple values"


def _is_unbounded_homogeneous_tuple(*, elts: list[ast.expr]) -> bool:
    """Check whether a tuple[...] slice is the unbounded tuple[X, ...] form.

    Args:
        elts: The elements of the tuple subscript's slice.

    Returns:
        True if this is tuple[X, ...], homogeneous and unbounded,
        with no fixed positional meaning.
    """
    return (
        len(elts) == _UNBOUNDED_TUPLE_SLICE_LENGTH and isinstance(elts[1], ast.Constant) and elts[1].value is Ellipsis
    )


def _get_tuple_subscript_slice(*, annotation: ast.expr | None) -> ast.Tuple | None:
    """Return the tuple slice of a bare tuple[...] subscript annotation, if it is one.

    Args:
        annotation: The annotation to check.

    Returns:
        The tuple slice (tuple[A, B, ...]'s A, B, ...) if annotation
        is a bare tuple[...] subscript, otherwise None.
    """
    if not (isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name)):
        return None

    # tuple is Python's own builtin type name, not a magic value
    # pylint: disable=magic-value-comparison
    if annotation.value.id != "tuple" or not isinstance(annotation.slice, ast.Tuple):
        return None

    return annotation.slice


def is_bare_multi_value_tuple(*, annotation: ast.expr | None) -> bool:
    """Check whether a type annotation is a bare tuple[...] with 2+ fixed elements.

    Args:
        annotation: The annotation to check (a return annotation, a
            parameter annotation, or a variable/field annotation), or None.

    Returns:
        True if the annotation is tuple[A, B, ...]. With two or more
        distinct type arguments. False for an unbounded homogeneous
        tuple, tuple[X, ...], which has no positional meaning to
        confuse.
    """
    slice_node = _get_tuple_subscript_slice(annotation=annotation)
    if slice_node is None:
        return False

    elts = slice_node.elts
    if _is_unbounded_homogeneous_tuple(elts=elts):
        return False

    return len(elts) >= _MINIMUM_MULTI_VALUE_COUNT


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
    if positional_args and positional_args[0].arg in {"self", "cls"}:
        positional_args = positional_args[1:]

    total_params = len(positional_args) + len(node.args.kwonlyargs)
    return _ParameterCounts(positional_args=positional_args, total_params=total_params)


class _FunctionPredicateFun(Protocol):  # pylint: disable=too-few-public-methods
    """A function checking whether a function node violates some rule."""

    def __call__(self, *, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool: ...


class _AssignPredicateFun(Protocol):  # pylint: disable=too-few-public-methods
    """A function checking whether an annotated-assignment node violates some rule."""

    def __call__(self, *, node: ast.AnnAssign) -> bool: ...


def find_function_violations(
    *,
    nodes: list[ast.FunctionDef | ast.AsyncFunctionDef],
    predicate: _FunctionPredicateFun,
    rule: Rule,
) -> list[Violation]:
    """Flag every function node matching a predicate as a violation.

    Args:
        nodes: Every function node in the file, already collected by walk_once.
        predicate: Returns True for a function node that violates the rule.
        rule: Which rule to record the violation against.

    Returns:
        A list of violations found, one per matching function.
    """
    return [make_violation(node=node, rule=rule) for node in nodes if predicate(node=node)]


def find_assign_violations(
    *,
    nodes: list[ast.AnnAssign],
    predicate: _AssignPredicateFun,
    rule: Rule,
) -> list[Violation]:
    """Flag every annotated-assignment node matching a predicate as a violation.

    Args:
        nodes: Every annotated-assignment node in the file, already collected by walk_once.
        predicate: Returns True for an annotated assignment that violates the rule.
        rule: Which rule to record the violation against.

    Returns:
        A list of violations found, one per matching assignment.
    """
    return [make_violation(node=node, rule=rule) for node in nodes if predicate(node=node)]


class WalkedNodes(NamedTuple):
    """Every relevant node in a file, walked once and split by kind."""

    function_nodes: list[ast.FunctionDef | ast.AsyncFunctionDef]
    assign_nodes: list[ast.AnnAssign]
    call_statement_nodes: list[ast.Call]
    class_nodes: list[ast.ClassDef]


def call_statement_value(*, node: ast.AST) -> ast.Call | None:
    """Return a bare call-statement's inner Call node if the node is one.

    Args:
        node: A node encountered while walking the tree.

    Returns:
        The inner Call if node is an Expr wrapping a Call (a bare
        call-statement, its result discarded), otherwise None.
    """
    if not isinstance(node, ast.Expr):
        return None
    return node.value if isinstance(node.value, ast.Call) else None


# Single-pass node classification is the point of this function, splitting it further means walking the tree twice again
def walk_once(*, tree: ast.Module) -> WalkedNodes:  # complexipy: ignore
    """Walk a tree exactly once, splitting nodes by kind for every checker to reuse.

    Args:
        tree: The parsed AST of a Python source file.

    Returns:
        Every function, annotated-assignment, bare call-statement,
        and class definition node that is found.
    """
    function_nodes = []
    assign_nodes = []
    call_statement_nodes = []
    class_nodes = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_nodes.append(node)
        elif isinstance(node, ast.AnnAssign):
            assign_nodes.append(node)
        elif isinstance(node, ast.ClassDef):
            class_nodes.append(node)
        else:
            call_statement = call_statement_value(node=node)
            if call_statement is not None:
                call_statement_nodes.append(call_statement)
    return WalkedNodes(
        function_nodes=function_nodes,
        assign_nodes=assign_nodes,
        call_statement_nodes=call_statement_nodes,
        class_nodes=class_nodes,
    )
