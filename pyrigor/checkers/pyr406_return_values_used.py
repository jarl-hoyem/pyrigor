"""PYR406 checker: flag a discarded, non-None-returning local function call."""

import ast

from pyrigor.checkers._shared import WalkedNodes
from pyrigor.rules import Rule
from pyrigor.violations import Violation, make_violation

_NONE_ANNOTATION_NAME = "None"

_EXCLUDED_RETURN_NAMES = frozenset(
    {_NONE_ANNOTATION_NAME, "NoReturn", "Never", "Iterator", "Generator", "AsyncGenerator"}
)


def _simple_name(*, node: ast.expr) -> str | None:
    """Extract a Name or Attribute node's bare name.

    Args:
        node: The expression to inspect.

    Returns:
        The Name's `id`, the Attribute's `attr`, or None for any other node shape.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _resolve_constant(*, annotation: ast.Constant) -> str | None:
    """Resolve a Constant return annotation.

    Args:
        annotation: A Constant annotation node.

    Returns:
        "None" for an explicit -> None annotation, otherwise None.
    """
    return _NONE_ANNOTATION_NAME if annotation.value is None else None


def _resolve_union(*, op: ast.operator) -> str | None:
    """Resolve a BinOp return annotation's operator.

    Args:
        op: The BinOp's operator node.

    Returns:
        A synthetic "UnionType" name if this is a PEP 604 union
        (`X | Y`, using BitOr), otherwise None.
    """
    return "UnionType" if isinstance(op, ast.BitOr) else None


def _annotation_name(*, annotation: ast.expr | None) -> str | None:
    """Extract the base name of a return annotation, resolving through a subscript.

    Args:
        annotation: A function's return annotation, or None.

    Returns:
        "None" for an explicit -> None annotation, the bare name for
        a Name or Attribute annotation (including the base of a
        subscripted generic like Iterator[X]), a synthetic "UnionType"
        name for a PEP 604 union (X | Y), or None if there is no
        annotation, or it doesn't resolve to a simple name.
    """
    if annotation is None:
        return None
    if isinstance(annotation, ast.Constant):
        return _resolve_constant(annotation=annotation)
    if isinstance(annotation, ast.Subscript):
        return _annotation_name(annotation=annotation.value)
    if isinstance(annotation, ast.BinOp):
        return _resolve_union(op=annotation.op)
    return _simple_name(node=annotation)


def _is_method(*, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check whether a function definition's first parameter is self/cls.

    Args:
        node: The function definition to check.

    Returns:
        True if this looks like a method, called via attribute access
        (self.foo()/obj.foo()) rather than a bare name. PYR406 only
        matches bare-name calls, so a method's name must not enter
        the protected set — nothing bare-name-calls it, and treating
        it as protected would risk flagging an unrelated bare call
        that happens to share the method's name.
    """
    positional_args = list(node.args.posonlyargs) + list(node.args.args)
    return bool(positional_args) and positional_args[0].arg in ("self", "cls")


def _is_protected_return(*, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check whether a function's return value must be used at every call site.

    Args:
        node: The function definition to check.

    Returns:
        True if the function has a return annotation other than None,
        NoReturn/Never (nothing to discard), or a generator annotation
        (Iterator/Generator/AsyncGenerator — covered by PYR407 instead).
    """
    name = _annotation_name(annotation=node.returns)
    return name is not None and name not in _EXCLUDED_RETURN_NAMES


def _protected_function_names(*, function_nodes: list[ast.FunctionDef | ast.AsyncFunctionDef]) -> set[str]:
    """Collect the names of every locally defined function whose return value must be used.

    Args:
        function_nodes: Every function definition in the file.

    Returns:
        The set of function names in scope for PYR406, excluding
        likely methods (see _is_method).
    """
    return {node.name for node in function_nodes if _is_protected_return(node=node) and not _is_method(node=node)}


def find_violations(*, nodes: WalkedNodes) -> list[Violation]:
    """Find PYR406 violations in already-walked nodes.

    Args:
        nodes: Every relevant node in the file, from walk_once.

    Returns:
        A list of violations, one per bare-statement call to a
        locally defined, non-None-returning function.
    """
    protected_names = _protected_function_names(function_nodes=nodes.function_nodes)
    return [
        make_violation(node=call, rule=Rule.PYR406)
        for call in nodes.call_statement_nodes
        if isinstance(call.func, ast.Name) and call.func.id in protected_names
    ]
