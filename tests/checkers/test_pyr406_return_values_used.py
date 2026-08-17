"""Tests for the PYR406 checker (return values used)."""

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
    """An annotation shape PYR406 doesn't resolve to a simple name (a union) should not be flagged."""
    source = """
def compute_total(items) -> int | str:
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


def test_no_violation_for_method_call_via_self() -> None:
    """A method (leading self) called via self.foo() uses attribute access, out of PYR406's bare-name scope."""
    source = """
class Foo:
    def compute_total(self, items) -> float:
        ...

    def handle(self, items):
        self.compute_total(items)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations


def test_no_violation_for_lambda_call() -> None:
    """A lambda assigned to a name and called bare is not a FunctionDef, so it is outside PYR406's scope."""
    source = """
compute_total = lambda items: sum(items)

compute_total(items)
"""
    violations = find_violations(nodes=walk_once(tree=ast.parse(source)))

    assert not violations
