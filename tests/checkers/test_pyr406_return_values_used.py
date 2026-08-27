"""Tests for the PYR406 checker (return values used)."""
# test assertions compare against expected literal values by design,
# not a magic-value problem
# pylint: disable=magic-value-comparison

import ast

# noinspection PyProtectedMember
from pyrigor.checkers._shared import walk_once
from pyrigor.checkers.pyr406_return_values_used import find_violations


def test_flags_bare_call_to_local_function_with_non_none_return() -> None:
    """A bare call to a locally defined, non-None-returning function should be flagged."""
    source = """
def compute_total(items) -> float:
    ...

compute_total(items)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "compute_total"


def test_no_violation_when_return_value_is_assigned() -> None:
    """A call whose result is assigned should not be flagged."""
    source = """
def compute_total(items) -> float:
    ...

total = compute_total(items)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_no_violation_when_call_used_as_argument() -> None:
    """A call whose result is passed to another call, not discarded, should not be flagged."""
    source = """
def compute_total(items) -> float:
    ...

def log(value):
    ...

log(compute_total(items))
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_no_violation_for_function_returning_none() -> None:
    """A function explicitly annotated -> None should never be flagged, even if its call is bare."""
    source = """
def log_event(message) -> None:
    ...

log_event("started")
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_no_violation_for_unannotated_function() -> None:
    """A function with no return annotation at all is outside PYR406's scope (return type unknown)."""
    source = """
def compute_total(items):
    ...

compute_total(items)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_no_violation_for_noreturn_annotated_function() -> None:
    """A function annotated -> NoReturn never returns control, nothing to discard."""
    source = """
def fail(message) -> NoReturn:
    ...

fail("boom")
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_no_violation_for_never_annotated_function() -> None:
    """A function annotated `-> Never` never returns control, nothing to discard."""
    source = """
def fail(message) -> Never:
    ...

fail("boom")
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_no_violation_for_attribute_style_noreturn_annotation() -> None:
    """A NoReturn annotation written via attribute access (`typing.NoReturn`) should still be excluded."""
    source = """
def fail(message) -> typing.NoReturn:
    ...

fail("boom")
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_no_violation_for_unrecognized_annotation_shape() -> None:
    """An annotation shape PYR406 cannot resolve to a simple name (a call expression) should not be flagged."""
    source = """
def compute_total(items) -> some_registry.lookup("total"):
    ...

compute_total(items)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_no_violation_for_generator_annotated_function() -> None:
    """A generator-annotated function (Iterator[X]) is covered by PYR407 instead, not PYR406."""
    source = """
def iter_items(items) -> Iterator[int]:
    ...

iter_items(items)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_no_violation_for_external_function_call() -> None:
    """A call to a name that is not defined locally should never be flagged."""
    source = """
print(compute_elsewhere())
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_flags_bare_call_to_local_async_function_with_non_none_return() -> None:
    """A bare call to a locally defined, non-None-returning async function should be flagged."""
    source = """
async def compute_total(items) -> float:
    ...

compute_total(items)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "compute_total"


def test_flags_bare_call_to_nested_function() -> None:
    """A nested (non-method) function's discarded return value should still be flagged."""
    source = """
def outer():
    def helper() -> float:
        ...

    helper()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "helper"


def test_does_not_flag_shadowed_bare_function_with_none_return() -> None:
    """A local function shadowing a protected name must not be reported as protected."""
    source = """
def value() -> int:
    return 1

def outer() -> None:
    def value() -> None:
        return None
    value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))
    assert violations == []


def test_flags_protected_shadowing_local_function() -> None:
    """A protected local definition must still be reported despite an outer same-name function."""
    source = """
def value() -> None:
    return None

def outer() -> None:
    def value() -> int:
        return 1
    value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))
    assert len(violations) == 1


def test_ignores_unresolved_bare_call_inside_nested_function() -> None:
    """An unresolved name must not be inferred to return a protected value."""
    source = """
def outer() -> None:
    def helper() -> int:
        return 1
    missing()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))
    assert violations == []


def test_uses_last_same_scope_definition_for_bare_call() -> None:
    """Sequential redefinition follows Python's last-binding semantics."""
    source = """
def value() -> None:
    return None

def value() -> int:
    return 1

value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))
    assert len(violations) == 1


def test_does_not_flag_local_lambda_shadowing_protected_function() -> None:
    """A local non-function binding must stop outer-scope resolution."""
    source = """
def value() -> int:
    return 1

def outer() -> None:
    value = lambda: None
    value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))
    assert violations == []


def test_tracks_vararg_and_kwarg_bindings() -> None:
    """Argument bindings must also prevent the fallback to an outer function."""
    source = """
def value() -> int:
    return 1

def outer(value, *args, **kwargs):
    value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))
    assert violations == []


def test_does_not_flag_imported_name_shadowing_protected_function() -> None:
    """Imported names must stop fallback to an outer protected function."""
    for import_statement in ("import other as value", "from other import value"):
        source = f"""
def value() -> int:
    return 1

def outer() -> None:
    {import_statement}
    value()
"""
        violations = find_violations(nodes=walk_once(tree=ast.parse(source)))
        assert violations == []


def test_does_not_flag_exception_alias_shadowing_protected_function() -> None:
    """An exception alias must stop fallback to an outer-protected function."""
    source = """
def value() -> int:
    return 1

def outer() -> None:
    try:
        pass
    except Exception as value:
        value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))
    assert violations == []


def test_does_not_flag_match_binding_shadowing_protected_function() -> None:
    """A capture-pattern binding must stop fallback to an outer protected function."""
    source = """
def value() -> int:
    return 1

def outer(item) -> None:
    match item:
        case value:
            value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))
    assert violations == []


def test_tracks_star_and_mapping_pattern_bindings() -> None:
    """All named structural-pattern bindings must stop the outer lookup."""
    source = """
def value() -> int:
    return 1

def outer(item) -> None:
    match item:
        case [*value]:
            value()
        case {**value}:
            value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))
    assert violations == []


def test_does_not_flag_local_class_shadowing_protected_function() -> None:
    """A local class binding must stop fallback to an outer protected function."""
    source = """
def value() -> int:
    return 1

def outer() -> None:
    class value:
        pass
    value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))
    assert violations == []


def test_flags_nonlocal_protected_function_reference() -> None:
    """A nested function's nonlocal reference must resolve to its enclosing function."""
    source = """
def outer() -> None:
    def value() -> int:
        return 1

    def inner() -> None:
        nonlocal value
        value()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))
    assert len(violations) == 1


def test_flags_self_call_to_same_class_method() -> None:
    """A self.foo() call within a method of the same class that defines foo() should be flagged."""
    source = """
class Foo:
    def compute_total(self, items) -> float:
        ...

    def handle(self, items):
        self.compute_total(items)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "compute_total"


def test_flags_self_call_to_staticmethod() -> None:
    """A self.foo() call to a staticmethod defined on the same class should still be flagged."""
    source = """
class Foo:
    @staticmethod
    def compute_total(items) -> float:
        ...

    def handle(self, items):
        self.compute_total(items)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "compute_total"


def test_no_violation_for_self_call_to_inherited_method() -> None:
    """A self.foo() call where foo() is inherited, not defined directly on this class, is not detected."""
    source = """
class Base:
    def compute_total(self, items) -> float:
        ...

class Foo(Base):
    def handle(self, items):
        self.compute_total(items)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_no_violation_for_classmethod_call_via_cls() -> None:
    """A cls.foo() call is out of scope for this pass — same-class detection covers self only."""
    source = """
class Foo:
    @classmethod
    def compute_total(cls, items) -> float:
        ...

    @classmethod
    def handle(cls, items):
        cls.compute_total(items)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_no_violation_for_nested_class_with_own_self() -> None:
    """A nested class's own self.foo() call must not be attributed to the enclosing class."""
    source = """
class Outer:
    def handle(self):
        class Inner:
            def method(self):
                self.foo()

    def foo(self) -> float:
        ...
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_flags_self_call_via_nested_closure() -> None:
    """A self.foo() call inside a closure nested within a method is still same-class self, still flagged."""
    source = """
class Foo:
    def compute_total(self, items) -> float:
        ...

    def handle(self, items):
        def inner():
            self.compute_total(items)
        inner()
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "compute_total"


def test_no_violation_for_lambda_call() -> None:
    """A lambda assigned to a name and called bare is not a FunctionDef, so it is outside PYR406's scope."""
    source = """
compute_total = lambda items: sum(items)

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


def test_flags_bare_call_for_pep604_union_return() -> None:
    """A PEP 604 union return (`int | str`) must still have its return value used."""
    source = """
def compute_total(items) -> int | str:
    ...

compute_total(items)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "compute_total"


def test_flags_bare_call_for_pep604_union_with_none() -> None:
    """A PEP 604 union that includes None (`int | None`) must still have its return value used."""
    source = """
def parse(s) -> int | None:
    ...

parse(s)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "parse"


def test_flags_bare_call_for_chained_pep604_union() -> None:
    """A chained PEP 604 union (`int | str | None`) must still have its return value used."""
    source = """
def compute_total(items) -> int | str | None:
    ...

compute_total(items)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert len(violations) == 1
    assert violations[0].context_name == "compute_total"


def test_no_violation_for_non_union_binop_annotation() -> None:
    """A BinOp annotation that is not a union (for example, arithmetic) should not be treated as protected."""
    source = """
def compute_total(items) -> int + str:
    ...

compute_total(items)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations
