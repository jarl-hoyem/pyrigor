"""PYR406 checker: flag a discarded, non-None-returning local function call."""

import ast
from collections.abc import Iterator
from typing import Final, NamedTuple

from pyrigor.checkers._shared import (
    WalkedNodes,
    call_statement_value,
    function_scopes,
    nearest_function_scope,
)
from pyrigor.finding_builder import FindingContext, make_finding
from pyrigor.findings import Finding
from pyrigor.rules import Rule

_NONE_ANNOTATION_NAME: Final = "None"

_EXCLUDED_RETURN_NAMES: Final = frozenset(
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


def _resolve_union(*, op: ast.operator) -> str | None:
    """Resolve a BinOp return annotation's operator.

    Args:
        op: The BinOp's operator node.

    Returns:
        A synthetic "UnionType" name if this is a PEP 604 union
        (`X | Y`, using BitOr), otherwise None.
    """
    return "UnionType" if isinstance(op, ast.BitOr) else None


def _quoted_annotation_name(*, annotation: ast.Constant) -> str | None:
    """Resolve a quoted return annotation by reading its text as the expression it names.

    Args:
        annotation: A constant annotation. It names a type only when its value is a string.

    Returns:
        What the same annotation written without quotes would resolve to. None if the value is not a string, if the
        text is not an expression Python can parse, or if the text is itself a constant, such as a nested string or a
        quoted None. Python rejects those as types too.
    """
    if not isinstance(annotation.value, str):
        return None
    try:
        expression = ast.parse(annotation.value, mode="eval").body
    except (SyntaxError, ValueError, RecursionError):
        # ValueError is what Python 3.11 raises for a null byte, and RecursionError what a huge expression raises.
        return None
    if isinstance(expression, ast.Constant):
        return None
    return _annotation_name(annotation=expression)


def _annotation_name(*, annotation: ast.expr | None) -> str | None:
    """Extract the base name of a return annotation, resolving through a subscript.

    Args:
        annotation: A function's return annotation, or None.

    Returns:
        The bare name for a Name or Attribute annotation (including
        the base of a subscripted generic like Iterator[X]), a
        synthetic "UnionType" name for a PEP 604 union (X | Y), or
        None if there is no annotation, or it does not otherwise
        resolve to a simple name. A quoted annotation resolves like
        the same annotation written without quotes. A constant that
        is not such a string, including an explicit -> None, needs no
        name of its own: _is_protected_return already treats "no
        name" as unprotected, the same outcome an explicit -> None
        reaches through _EXCLUDED_RETURN_NAMES.
    """
    if annotation is None:
        return None
    if isinstance(annotation, ast.Constant):
        return _quoted_annotation_name(annotation=annotation)
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


_NamesByScope = dict[ast.AST, dict[str, list[ast.AST]]]


class _ScopeBindings(NamedTuple):
    """The name bindings of a file, as Python scopes them.

    A name that a function declares global is never local to it, so its bindings in that function belong to the
    module scope, as in Python's own scope analysis. They are also kept per declaring function, because inside that
    function the order of its own stores decides what a call reaches.
    """

    lexical: _NamesByScope
    global_stores: _NamesByScope
    declared_global: dict[ast.AST, set[str]]


def _global_scope(*, node: ast.Global, parents: dict[ast.AST, ast.AST]) -> ast.AST | None:
    """Find the function scope that a global statement declares names in, or None when it declares nothing.

    A global statement at module level has no effect, and one in a class body belongs to the class.
    """
    if _inside_class_body(node=node, parents=parents):
        return None
    scope = nearest_function_scope(node=node, parents=parents)
    return None if isinstance(scope, ast.Module) else scope


def _global_declarations(*, nodes: WalkedNodes) -> dict[ast.AST, set[str]]:
    """Collect the names that each function scope declares global."""
    declared: dict[ast.AST, set[str]] = {}
    for node in nodes.parents:
        if isinstance(node, ast.Global):
            scope = _global_scope(node=node, parents=nodes.parents)
            if scope is not None:
                declared.setdefault(scope, set()).update(node.names)
    return declared


def _bound_nodes_by_scope(*, nodes: WalkedNodes) -> _ScopeBindings:
    """Collect name-binding nodes by scope, in source order."""
    bindings = _ScopeBindings(lexical={}, global_stores={}, declared_global=_global_declarations(nodes=nodes))
    for node in nodes.parents:
        if _inside_class_body(node=node, parents=nodes.parents):
            continue
        if _is_comprehension_target(node=node, parents=nodes.parents):
            continue
        scope = nearest_function_scope(node=node, parents=nodes.parents)
        _add_bindings(bindings=bindings, scope=scope, node=node, parents=nodes.parents)
    return bindings


def _add_bindings(*, bindings: _ScopeBindings, scope: ast.AST, node: ast.AST, parents: dict[ast.AST, ast.AST]) -> None:
    """Add one node's bindings to the scope that holds each name, which is the module for a global name."""
    for name in _node_bindings(node=node):
        if name in bindings.declared_global.get(scope, set()):
            bindings.global_stores.setdefault(scope, {}).setdefault(name, []).append(node)
            holder = list(function_scopes(scope=scope, parents=parents))[-1]
        else:
            holder = scope
        bindings.lexical.setdefault(holder, {}).setdefault(name, []).append(node)


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
    # noinspection PyTypeChecker
    parent = _nearest_comprehension(node=node, parents=parents)
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
    # noinspection PyTypeChecker
    return any(candidate is node for candidate in ast.walk(comprehension.target))


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
    """Return a name only when the node binds it in its enclosing scope."""
    return {node.id} if isinstance(node.ctx, (ast.Store, ast.Del)) else set()


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


class _BindingPosition(NamedTuple):
    """A binding node's source-order position."""

    line: int
    column: int


def _binding_position(*, node: ast.AST) -> _BindingPosition:
    """Return a binding node's source-order position.

    Raises:
        ValueError: If the node has no line or column. Every node shape _node_bindings can
            actually produce (Name, arg, ExceptHandler, MatchAs/MatchStar/MatchMapping,
            Import/ImportFrom, ClassDef, FunctionDef/AsyncFunctionDef) always having both.
    """
    lineno = getattr(node, "lineno", None)
    col_offset = getattr(node, "col_offset", None)
    if lineno is None or col_offset is None:
        raise ValueError("binding has no position")
    return _BindingPosition(line=lineno, column=col_offset)


_BranchArms = dict[ast.AST, int]


def _arm_index(*, child: ast.AST, parent: ast.AST) -> int | None:
    """Return which arm of an if statement or a match statement a child sits in, or None when it sits in neither."""
    if isinstance(parent, ast.Match) and isinstance(child, ast.match_case):
        return parent.cases.index(child)
    if isinstance(parent, ast.If) and child is not parent.test:
        return int(child in parent.orelse)
    return None


def _branch_arms(*, node: ast.AST, parents: dict[ast.AST, ast.AST]) -> _BranchArms:
    """Map each if or match statement that holds a node within its scope to the arm that holds it."""
    parent = parents.get(node)
    if parent is None or isinstance(parent, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef)):
        return {}
    arms = _branch_arms(node=parent, parents=parents)
    index = _arm_index(child=node, parent=parent)
    if index is not None:
        arms[parent] = index
    return arms


def _in_other_arm(*, arms: _BranchArms, other: _BranchArms) -> bool:
    """Check whether two nodes sit in different arms of one branching statement so that both never run."""
    return any(other.get(statement, arm) != arm for statement, arm in arms.items())


def _runs_with(*, arms: _BranchArms, other: _BranchArms) -> bool:
    """Check whether every arm that holds a node also holds the other, so the node runs whenever the other does."""
    return all(other.get(statement) == arm for statement, arm in arms.items())


def _is_replaced(
    *, binding: ast.AST, possible: list[ast.AST], arms: dict[ast.AST, _BranchArms], call_arms: _BranchArms
) -> bool:
    """Check whether a later binding runs on every path to the call from this one, which leaves this one unreachable."""
    position = _binding_position(node=binding)
    return any(
        _binding_position(node=later) > position
        and (_runs_with(arms=arms[later], other=arms[binding]) or _runs_with(arms=arms[later], other=call_arms))
        for later in possible
    )


def _possible_bindings(
    *, bindings: list[ast.AST], arms: dict[ast.AST, _BranchArms], call_arms: _BranchArms
) -> list[ast.AST]:
    """Keep the bindings that are not in another arm than the call's own."""
    return [node for node in bindings if not _in_other_arm(arms=arms[node], other=call_arms)]


def _reaching_bindings(*, call: ast.Call, bindings: list[ast.AST], parents: dict[ast.AST, ast.AST]) -> list[ast.AST]:
    """List the bindings that can be the one a call reaches.

    Only an if statement and a match statement count as alternative paths, so a loop or a try statement stays
    sequential. A binding in another arm than the call's own never runs before it. A later binding replaces an earlier
    one when it runs whenever the earlier one does or whenever the call does. A binding inside a branch therefore
    leaves the bindings before the branch is reachable.
    """
    call_arms = _branch_arms(node=call, parents=parents)
    arms = {node: _branch_arms(node=node, parents=parents) for node in bindings}
    possible = _possible_bindings(bindings=bindings, arms=arms, call_arms=call_arms)
    return [
        node for node in possible if not _is_replaced(binding=node, possible=possible, arms=arms, call_arms=call_arms)
    ]


def _binding_is_protected(
    *, call: ast.Call, bindings: list[ast.AST], protected_names: set[str], parents: dict[ast.AST, ast.AST]
) -> bool:
    """Check whether any binding that a call can reach is a protected definition."""
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _is_protected_definition(call=call, definitions=[node], protected_names=protected_names)
        for node in _reaching_bindings(call=call, bindings=bindings, parents=parents)
    )


def _own_global_bindings(
    *, call: ast.Call, name: str, scope: ast.AST, bindings: _ScopeBindings, parents: dict[ast.AST, ast.AST]
) -> list[ast.AST] | None:
    """List what a call reaches when its own function declares the name global, or None when it does not.

    A store in the same function that comes before the call decides it. Without one, the call reaches what the module
    holds, except the function's own later stores, which have not run yet.
    """
    if name not in bindings.declared_global.get(scope, set()):
        return None
    own = bindings.global_stores.get(scope, {}).get(name, [])
    call_position = _binding_position(node=call)
    before = [node for node in own if _binding_position(node=node) < call_position]
    if before:
        return before
    return _module_bindings_without(name=name, excluded=own, scope=scope, bindings=bindings, parents=parents)


def _module_bindings_without(
    *, name: str, excluded: list[ast.AST], scope: ast.AST, bindings: _ScopeBindings, parents: dict[ast.AST, ast.AST]
) -> list[ast.AST]:
    """List the module's bindings of a name, leaving out the given nodes."""
    module = list(function_scopes(scope=scope, parents=parents))[-1]
    return [node for node in bindings.lexical.get(module, {}).get(name, []) if node not in excluded]


def _reachable_bindings(
    *, call: ast.Call, name: str, scope: ast.AST, bindings: _ScopeBindings, parents: dict[ast.AST, ast.AST]
) -> list[ast.AST]:
    """List the bindings that a call to a name reaches, from the innermost scope that holds any."""
    own = _own_global_bindings(call=call, name=name, scope=scope, bindings=bindings, parents=parents)
    if own is not None:
        return own
    for candidate_scope in function_scopes(scope=scope, parents=parents):
        found = bindings.lexical.get(candidate_scope, {}).get(name, [])
        if found:
            return found
    return []


def _bare_call_is_protected(
    *,
    call: ast.Call,
    nodes: WalkedNodes,
    protected_names: set[str],
    bindings: _ScopeBindings,
) -> bool:
    """Resolve one bare call through its scopes."""
    if not isinstance(call.func, ast.Name) or _inside_class_body(node=call, parents=nodes.parents):
        return False
    scope = nearest_function_scope(node=call, parents=nodes.parents)
    found = _reachable_bindings(call=call, name=call.func.id, scope=scope, bindings=bindings, parents=nodes.parents)
    return _binding_is_protected(call=call, bindings=found, protected_names=protected_names, parents=nodes.parents)


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


def _same_class_findings(*, class_def: ast.ClassDef) -> list[ast.Call]:
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
    bindings = _bound_nodes_by_scope(nodes=nodes)
    return [
        call
        for call in nodes.call_statement_nodes
        if _bare_call_is_protected(
            call=call,
            nodes=nodes,
            protected_names=protected_names,
            bindings=bindings,
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
    return [call for class_def in class_nodes for call in _same_class_findings(class_def=class_def)]


def find_findings(*, nodes: WalkedNodes, context: FindingContext) -> list[Finding]:
    """Find PYR406 findings in already-walked nodes.

    Args:
        nodes: Every relevant node in the file, from walk_once.
        context: Source positions and names used to build findings.

    Returns:
        A list of findings: one per bare-statement call to a
        locally defined, non-None-returning function, whether called
        by bare name or, when defined on the same class, via self.
    """
    protected_names = _protected_function_names(function_nodes=nodes.function_nodes)
    matched_calls = _bare_name_call_matches(nodes=nodes, protected_names=protected_names) + _same_class_call_matches(
        class_nodes=nodes.class_nodes,
    )
    return [make_finding(node=call, rule=Rule.PYR406, context=context) for call in matched_calls]
