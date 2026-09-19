"""Tests for PYR406's scope and binding resolution (which definition a bare name resolves to)."""
# test assertions compare against expected literal values by design,
# not a magic-value problem
# pylint: disable=magic-value-comparison

import ast

import pytest

# noinspection PyProtectedMember
from pyrigor.checkers._shared import walk_once

# noinspection PyProtectedMember
from pyrigor.checkers.pyr406_return_values_used import (
    _binding_position,  # pyright: ignore[reportPrivateUsage]
    find_violations,
)


def test_comprehension_target_does_not_shadow_outer_protected_function() -> None:
    """Python 3 comprehension targets are local to the comprehension, not the enclosing function."""
    source = """
def compute_total(items) -> float:
    ...

def handle(items):
    [compute_total for compute_total in items]
    compute_total(items)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "compute_total"


def test_tuple_comprehension_target_does_not_shadow_outer_protected_function() -> None:
    """A name inside a tuple target is still comprehension-local.

    A bare target's parent is the comprehension itself, so only a nested target reaches the
    walk towards the nearest enclosing comprehension.
    """
    source = """
def compute_total(items) -> float:
    ...

def handle(pairs):
    [first for (compute_total, first) in pairs]
    compute_total(pairs)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "compute_total"


def test_class_body_binding_does_not_shadow_module_function() -> None:
    """A class body's local binding must not leak into the enclosing module scope."""
    source = """
def compute_total(items) -> float:
    ...

class Example:
    compute_total = lambda items: None

compute_total(items)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "compute_total"


def test_class_body_bare_call_is_out_of_scope() -> None:
    """Bare calls in a class body are not resolved as function-scope calls by PYR406."""
    source = """
def compute_total(items) -> float:
    ...

class Example:
    compute_total(items)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_no_violation_when_protected_function_is_rebound_by_lambda() -> None:
    """A later lambda binding replaces the protected function for bare-name resolution."""
    source = """
def compute_total(items) -> float:
    ...

compute_total = lambda items: None
compute_total(items)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_no_violation_when_protected_function_is_rebound_by_import() -> None:
    """A later import binding replaces the protected function for bare-name resolution."""
    source = """
def compute_total(items) -> float:
    ...

from other import compute_total
compute_total(items)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_later_lambda_binding_stops_outer_function_resolution() -> None:
    """A later local binding makes the name local for the whole function."""
    source = """
def value() -> int:
    return 1

def outer() -> None:
    value()
    value = lambda: None
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert violations == []


def test_later_import_binding_stops_outer_function_resolution() -> None:
    """A later import makes the name local for the whole function."""
    source = """
def value() -> int:
    return 1

def outer() -> None:
    value()
    from other import value
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert violations == []


def test_comprehension_target_does_not_shadow_before_or_after_comprehension() -> None:
    """A comprehension target remains local to its comprehension."""
    source = """
def value() -> int:
    return 1

def outer(items) -> None:
    value()
    [value for value in items]
    value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 2


def test_class_body_binding_does_not_shadow_calls_before_or_after_class() -> None:
    """A class-body binding never leaks into the enclosing module scope."""
    source = """
def value() -> int:
    return 1

value()

class Example:
    value = lambda: None

value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 2


def test_class_body_binding_does_not_stop_collecting_later_bindings() -> None:
    """A skipped class-body binding does not end the scan of the remaining bindings.

    The class comes first here, so a scan that stopped at it would miss the shadow below and
    fall back to the module-level function.
    """
    source = """
class Holder:
    attribute = 1

def value() -> int:
    return 1

def outer() -> None:
    value = None
    value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert violations == []


# The shadowing tests below share the value/outer fixture convention every other test in
# this suite already uses. Each is an independent, self-contained example of a distinct
# scenario, so nothing here needs to stay in sync with its counterpart in
# test_pyr406_return_values_used.py.
# pylint: disable=duplicate-code
def test_later_assignment_stops_outer_function_resolution() -> None:
    """A later assignment makes the name local for the whole function."""
    source = """
def value() -> int:
    return 1

def outer() -> None:
    value()
    value = None
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert violations == []


def test_loop_target_stops_outer_function_resolution() -> None:
    """A loop target binds in its enclosing function scope."""
    source = """
def value() -> int:
    return 1

def outer(items) -> None:
    for value in items:
        value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert violations == []


def test_context_manager_target_stops_outer_function_resolution() -> None:
    """A context-manager target binds in its enclosing function scope."""
    source = """
def value() -> int:
    return 1

def outer() -> None:
    with resource() as value:
        value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert violations == []


def test_global_declaration_resolves_to_module_function() -> None:
    """A global declaration resolves a bare call to the module-level function."""
    source = """
def value() -> int:
    return 1

def outer() -> None:
    global value
    value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "value"


def test_named_expression_target_stops_outer_function_resolution() -> None:
    """A named-expression target binds in its enclosing function scope."""
    source = """
def value() -> int:
    return 1

def outer(item) -> None:
    (value := item)
    value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert violations == []


def test_later_nested_function_definition_stops_outer_function_resolution() -> None:
    """A later nested function definition makes the name local for the whole function."""
    source = """
def value() -> int:
    return 1

def outer() -> None:
    value()

    def value() -> None:
        return None
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert violations == []


def test_augmented_assignment_stops_outer_function_resolution() -> None:
    """An augmented assignment makes the name local for the whole function."""
    source = """
def value() -> int:
    return 1

def outer() -> None:
    value()
    value += 1
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert violations == []


def test_delete_target_stops_outer_function_resolution() -> None:
    """A delete target makes the name local for the whole function."""
    source = """
def value() -> int:
    return 1

def outer() -> None:
    value()
    del value
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert violations == []


def test_named_expression_in_comprehension_stops_outer_function_resolution() -> None:
    """A comprehension-named expression binds in its containing function scope."""
    source = """
def value() -> int:
    return 1

def outer(items) -> None:
    [(value := item) for item in items]
    value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert violations == []


def test_named_expression_in_a_comprehension_condition_binds_in_the_enclosing_scope() -> None:
    """A named expression binds in the enclosing scope from the condition as well as the element.

    The condition sits outside the comprehension's target, which is what separates a leaking
    named expression from a comprehension-local loop variable.
    """
    source = """
def value() -> int:
    return 1

def outer(items) -> None:
    [item for item in items if (value := item)]
    value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert violations == []


def test_plain_dotted_import_stops_outer_function_resolution() -> None:
    """A plain dotted import binds its first component in the local scope."""
    source = """
def value() -> int:
    return 1

def outer() -> None:
    import value.helper
    value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert violations == []


def test_aliased_from_import_does_not_shadow_outer_function() -> None:
    """An aliased from-import leaves the original name available to the outer scope."""
    source = """
def value() -> int:
    return 1

def outer() -> None:
    from other import value as other_value
    value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "value"


def test_destructuring_loop_target_stops_outer_function_resolution() -> None:
    """Every name in a loop target binds in its enclosing function scope."""
    source = """
def value() -> int:
    return 1

def outer(items) -> None:
    for _, value in items:
        value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert violations == []


def test_destructuring_context_target_stops_outer_function_resolution() -> None:
    """Every name in a context-manager target binds in its enclosing function scope."""
    source = """
def value() -> int:
    return 1

def outer() -> None:
    with resource() as (_, value):
        value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert violations == []


def test_does_not_flag_bare_call_when_name_is_rebound_to_a_class() -> None:
    """A module-level name reassigned to a class before the call resolves to that binding, not the function."""
    source = """
def helper() -> int:
    return 1

class helper:
    pass

helper()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert violations == []


@pytest.mark.parametrize(
    "node",
    [
        pytest.param(ast.Name(id="x"), id="no-position"),
        pytest.param(ast.Name(id="x", lineno=1), id="no-col_offset"),
        pytest.param(ast.Name(id="x", col_offset=0), id="no-lineno"),
    ],
)
def test_binding_position_rejects_a_node_missing_either_field(*, node: ast.AST) -> None:
    """A binding needs both a line and a column, so a node missing either is rejected."""
    with pytest.raises(ValueError, match=r"^binding has no position$"):
        _binding_position(node=node)
