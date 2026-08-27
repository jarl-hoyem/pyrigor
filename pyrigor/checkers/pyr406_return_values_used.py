"""PYR406 checker: flag a discarded, non-None-returning local function call."""

import ast
from collections.abc import Iterator
from typing import cast

from pyrigor.checkers._shared import (
    WalkedNodes,
    call_statement_value,
    function_scopes,
    nearest_function_scope,
)
from pyrigor.rules import Rule
from pyrigor.violations import Violation, make_violation

_NONE_ANNOTATION_NAME = "None"

_EXCLUDED_RETURN_NAMES = frozenset(
    {_NONE_ANNOTATION_NAME, "NoReturn", "Never", "Iterator", "Generator", "AsyncGenerator"},
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
        annotation, or it does not resolve to a simple name.
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
    return bool(positional_args) and positional_args[0].arg in {"self", "cls"}


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
    """Collect protected names for compatibility with the shared checker API.

    Args:
        function_nodes: Every function definition in the file.

    Returns:
        The set of function names in scope for PYR406, excluding
        likely methods (see _is_method).
    """
    return {node.name for node in function_nodes if _is_protected_return(node=node) and not _is_method(node=node)}


def _is_protected_definition(
    *, call: ast.Call, definitions: list[ast.FunctionDef | ast.AsyncFunctionDef], protected_names: set[str]
) -> bool:
    """Check whether a call resolves to the last protected definition in scope."""
    return (
        bool(definitions)
        and isinstance(call.func, ast.Name)
        and call.func.id in protected_names
        and _is_protected_return(node=definitions[-1])
    )


def _bound_nodes_by_scope(*, nodes: WalkedNodes) -> dict[ast.AST, dict[str, list[ast.AST]]]:
    """Collect name-binding nodes by lexical scope, in source order."""
    bound: dict[ast.AST, dict[str, list[ast.AST]]] = {}
    for node in nodes.parents:
        if _inside_class_body(node=node, parents=nodes.parents):
            continue
        if _is_comprehension_target(node=node, parents=nodes.parents):
            continue
        scope = nearest_function_scope(node=node, parents=nodes.parents)
        _add_bindings(bound=bound, scope=scope, node=node)
    return bound


def _add_bindings(*, bound: dict[ast.AST, dict[str, list[ast.AST]]], scope: ast.AST, node: ast.AST) -> None:
    """Add one node's bindings to its lexical scope."""
    for name in _node_bindings(node=node):
        bound.setdefault(scope, {}).setdefault(name, []).append(node)


def _inside_class_body(*, node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """Return whether a node belongs to a class body rather than a method body."""
    parent = parents.get(node)
    if parent is None or isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    if isinstance(parent, ast.ClassDef):
        return True
    return _inside_class_body(node=parent, parents=parents)


def _is_comprehension_target(*, node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """Return whether a node binds a name in a comprehension-local target."""
    if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Store):
        return False
    current = cast("ast.AST", cast("object", node))
    parent = _nearest_comprehension(node=current, parents=parents)
    return parent is not None and _is_in_target(node=node, comprehension=parent)


def _nearest_comprehension(*, node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.comprehension | None:
    """Find the nearest enclosing comprehension unless a new lexical scope intervenes."""
    parent = parents.get(node)
    if isinstance(parent, ast.comprehension):
        return parent
    if parent is None or isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return None
    return _nearest_comprehension(node=parent, parents=parents)


def _is_in_target(*, node: ast.Name, comprehension: ast.comprehension) -> bool:
    """Return whether a name belongs to a comprehension's target expression."""
    target = cast("ast.AST", cast("object", comprehension.target))
    return any(candidate is node for candidate in ast.walk(target))


def _node_bindings(*, node: ast.AST) -> set[str]:
    """Return names bound by one AST node."""
    if isinstance(node, ast.Name):
        return _stored_name(node=node)
    if isinstance(node, ast.arg):
        return {node.arg}
    return _other_node_bindings(node=node)


def _other_node_bindings(*, node: ast.AST) -> set[str]:
    """Return bindings for non-name, non-argument nodes."""
    if isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar, ast.MatchMapping)):
        return _pattern_bindings(node=node)
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return _import_bindings(node=node)
    if isinstance(node, ast.ClassDef):
        return {node.name}
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return set()
    return {node.name, *_function_argument_names(node=node)}


def _pattern_bindings(*, node: ast.ExceptHandler | ast.MatchAs | ast.MatchStar | ast.MatchMapping) -> set[str]:
    """Return names introduced by an exception alias or match pattern."""
    name = getattr(node, "name", None) or getattr(node, "rest", None)
    return {name} if name else set()


def _import_bindings(*, node: ast.Import | ast.ImportFrom) -> set[str]:
    """Return names introduced by an import statement."""
    return {_import_alias_name(alias=alias, is_plain_import=isinstance(node, ast.Import)) for alias in node.names}


def _stored_name(*, node: ast.Name) -> set[str]:
    """Return a name only when the node stores it."""
    return {node.id} if isinstance(node.ctx, ast.Store) else set()


def _import_alias_name(*, alias: ast.alias, is_plain_import: bool) -> str:
    """Return the local name introduced by one import alias."""
    if alias.asname:
        return alias.asname
    return alias.name.split(".")[0] if is_plain_import else alias.name


def _function_argument_names(*, node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Return all argument names belonging to a function scope."""
    names = {arg.arg for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)}
    if node.args.vararg:
        names.add(node.args.vararg.arg)
    if node.args.kwarg:
        names.add(node.args.kwarg.arg)
    return names


def _latest_binding(*, bindings: list[ast.AST]) -> ast.AST:
    """Return the effective source-order binding from a non-empty list."""
    return max(bindings, key=lambda node: (int(getattr(node, "lineno", 0)), int(getattr(node, "col_offset", 0))))


def _binding_is_protected(*, call: ast.Call, bindings: list[ast.AST], protected_names: set[str]) -> bool:
    """Classify the effective binding for a name at one call site."""
    latest = _latest_binding(bindings=bindings)
    return isinstance(latest, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_protected_definition(
        call=call,
        definitions=[latest],
        protected_names=protected_names,
    )


def _bare_call_is_protected(
    *,
    call: ast.Call,
    nodes: WalkedNodes,
    protected_names: set[str],
    bound_nodes: dict[ast.AST, dict[str, list[ast.AST]]],
) -> bool:
    """Resolve one bare call through its lexical scopes."""
    if not isinstance(call.func, ast.Name):
        return False
    if _inside_class_body(node=call, parents=nodes.parents):
        return False
    scope = nearest_function_scope(node=call, parents=nodes.parents)
    for candidate_scope in function_scopes(scope=scope, parents=nodes.parents):
        bindings = bound_nodes.get(candidate_scope, {}).get(call.func.id, [])
        if bindings:
            return _binding_is_protected(call=call, bindings=bindings, protected_names=protected_names)
    return False


def _direct_methods(*, class_def: ast.ClassDef) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Collect a class's own direct method definitions, not a nested class's methods.

    Args:
        class_def: The class definition to inspect.

    Returns:
        Every FunctionDef/AsyncFunctionDef directly in the class body.
    """
    return [node for node in class_def.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _protected_method_names(*, class_def: ast.ClassDef) -> set[str]:
    """Collect a class's own method names whose return value must be used via self.

    Args:
        class_def: The class definition to inspect.

    Returns:
        The set of method names, directly defined on this class,
        whose return type is protected under PYR406.
    """
    return {method.name for method in _direct_methods(class_def=class_def) if _is_protected_return(node=method)}


def _iter_same_scope(*, node: ast.AST) -> Iterator[ast.AST]:
    """Yield every descendant of a node, without crossing into a nested class's own body.

    Args:
        node: The node to walk, typically a method body.

    Yields:
        Every descendant is reachable without descending into a nested
        ClassDef — its own `self` refers to its own instance, not
        the enclosing method's.
    """
    for child in ast.iter_child_nodes(node):
        yield child
        if not isinstance(child, ast.ClassDef):
            yield from _iter_same_scope(node=child)


def _self_call_name(*, call: ast.Call) -> str | None:
    """Extract the method name from a self.<name>() call if it is one.

    Args:
        call: A call node to inspect.

    Returns:
        The attribute name if `call.func` is `self.<name>`, otherwise None.
    """
    func = call.func
    # self is Python's own convention name, not a magic value
    # pylint: disable=magic-value-comparison
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "self":
        return func.attr
    return None


def _matched_self_call(*, node: ast.AST, protected_names: set[str]) -> ast.Call | None:
    """Check whether a node is a self.<name>() call matching a protected method name.

    Args:
        node: A node encountered while walking a method's body.
        protected_names: The enclosing class's own protected method names.

    Returns:
        The Call node if this is a bare self.<name>() call statement
        with <name> in protected_names, otherwise None.
    """
    call = call_statement_value(node=node)
    if call is None:
        return None
    return call if _self_call_name(call=call) in protected_names else None


def _same_scope_nodes(*, class_def: ast.ClassDef) -> Iterator[ast.AST]:
    """Yield every node reachable from a class's own methods, same-scope only.

    Args:
        class_def: The class definition to inspect.

    Yields:
        Every descendant node of the class's own direct
        methods (see _direct_methods, _iter_same_scope).
    """
    for method in _direct_methods(class_def=class_def):
        yield from _iter_same_scope(node=method)


def _same_class_violations(*, class_def: ast.ClassDef) -> list[ast.Call]:
    """Find self.<name>() calls within a class's own methods, matching a protected method.

    Args:
        class_def: The class definition to inspect.

    Returns:
        Every self.<name>() call-statement Call node is found within the
        class's own methods, where <name> is one of that same
        class's own protected method names.
    """
    protected_names = _protected_method_names(class_def=class_def)
    matches = (
        _matched_self_call(node=node, protected_names=protected_names)
        for node in _same_scope_nodes(class_def=class_def)
    )
    return [call for call in matches if call is not None]


def _bare_name_call_matches(*, nodes: WalkedNodes, protected_names: set[str]) -> list[ast.Call]:
    """Find bare-name calls to a locally defined, protected function.

    Args:
        nodes: Every relevant node in the file, from walk_once.
        protected_names: Names of protected, non-method functions.

    Returns:
        Every bare-statement Call node whose func is a Name matching
        a protected function name.
    """
    bound_nodes = _bound_nodes_by_scope(nodes=nodes)
    return [
        call
        for call in nodes.call_statement_nodes
        if _bare_call_is_protected(
            call=call,
            nodes=nodes,
            protected_names=protected_names,
            bound_nodes=bound_nodes,
        )
    ]


def _same_class_call_matches(*, class_nodes: list[ast.ClassDef]) -> list[ast.Call]:
    """Find self.<name>() calls across every class, matching that class's own protected methods.

    Args:
        class_nodes: Every class definition in the file.

    Returns:
        Every matching Call node, one class's results at a time,
        concatenated.
    """
    return [call for class_def in class_nodes for call in _same_class_violations(class_def=class_def)]


def find_violations(*, nodes: WalkedNodes) -> list[Violation]:
    """Find PYR406 violations in already-walked nodes.

    Args:
        nodes: Every relevant node in the file, from walk_once.

    Returns:
        A list of violations: one per bare-statement call to a
        locally defined, non-None-returning function, whether called
        by bare name or, when defined on the same class, via self.
    """
    protected_names = _protected_function_names(function_nodes=nodes.function_nodes)
    matched_calls = _bare_name_call_matches(nodes=nodes, protected_names=protected_names) + _same_class_call_matches(
        class_nodes=nodes.class_nodes,
    )
    return [make_violation(node=call, rule=Rule.PYR406) for call in matched_calls]
