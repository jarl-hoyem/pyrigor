"""Tests for the TypeGuard and TypeIs exemption shared by PYR402 and PYR403."""
# test assertions compare against expected literal values by design,
# not a magic-value problem

import ast

import pytest

from pyrigor.checkers import is_type_guard_function
from pyrigor.checkers.pyr402_keyword_only_arguments import find_findings as find_pyr402_findings
from pyrigor.checkers.pyr403_keyword_only_single_argument import find_findings as find_pyr403_findings
from tests.checker_helpers import check_source

_GUARD_ANNOTATIONS = [
    "TypeGuard[int]",
    "TypeIs[int]",
    "typing.TypeGuard[int]",
    "typing.TypeIs[int]",
    "typing_extensions.TypeGuard[int]",
    "typing_extensions.TypeIs[int]",
]
_NOT_GUARD_ANNOTATIONS = [
    "bool",
    "TypeGuard",
    "typing.TypeGuard",
    "Optional[TypeGuard[int]]",
    "list[TypeGuard[int]]",
    "typing.Foo[int]",
    "other.TypeGuard[int]",
    "a.b.TypeGuard[int]",
    "TG[int]",
    "'TypeGuard[int]'",
    "TypeGuard[int] | None",
]


def _function(*, source: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """Parse a source holding one function and return it."""
    node = ast.parse(source).body[0]
    assert isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    return node


@pytest.mark.parametrize("annotation", _GUARD_ANNOTATIONS)
def test_recognises_supported_guard_forms(*, annotation: str) -> None:
    """Bare, typing and typing_extensions forms of both guards are recognised."""
    assert is_type_guard_function(node=_function(source=f"def f(value) -> {annotation}: ..."))


@pytest.mark.parametrize("annotation", _NOT_GUARD_ANNOTATIONS)
def test_does_not_recognise_other_annotations(*, annotation: str) -> None:
    """Unsubscripted, wrapped, aliased, unrelated and quoted annotations are not guards."""
    assert not is_type_guard_function(node=_function(source=f"def f(value) -> {annotation}: ..."))


def test_function_without_return_annotation_is_not_a_guard() -> None:
    """A missing return annotation is not a guard."""
    assert not is_type_guard_function(node=_function(source="def f(value): ..."))


@pytest.mark.parametrize("annotation", _GUARD_ANNOTATIONS)
def test_single_guard_parameter_is_not_flagged(*, annotation: str) -> None:
    """A guard with only its narrowed value has nothing to make keyword-only."""
    source = f"def is_int(value) -> {annotation}: ..."

    assert not check_source(source=source, checker=find_pyr403_findings)
    assert not check_source(source=source, checker=find_pyr402_findings)


@pytest.mark.parametrize("annotation", _GUARD_ANNOTATIONS)
def test_guard_with_keyword_only_extra_is_not_flagged(*, annotation: str) -> None:
    """The narrowed value may stay positional when every other parameter is keyword-only."""
    source = f"def is_int(value, *, strict) -> {annotation}: ..."

    assert not check_source(source=source, checker=find_pyr402_findings)
    assert not check_source(source=source, checker=find_pyr403_findings)


@pytest.mark.parametrize("annotation", _GUARD_ANNOTATIONS)
def test_guard_with_further_positional_parameter_is_flagged_by_pyr402(*, annotation: str) -> None:
    """A positional parameter after the narrowed value still receives PYR402."""
    source = f"def is_int(value, strict) -> {annotation}: ..."

    findings = check_source(source=source, checker=find_pyr402_findings)

    assert len(findings) == 1
    assert findings[0].message.startswith("Function 'is_int' ")
    assert not check_source(source=source, checker=find_pyr403_findings)


@pytest.mark.parametrize("annotation", _NOT_GUARD_ANNOTATIONS)
def test_non_guard_annotation_keeps_existing_findings(*, annotation: str) -> None:
    """A return annotation that is not a guard leaves both rules unchanged."""
    single = f"def f(value) -> {annotation}: ..."
    several = f"def f(value, other) -> {annotation}: ..."

    assert len(check_source(source=single, checker=find_pyr403_findings)) == 1
    assert len(check_source(source=several, checker=find_pyr402_findings)) == 1


def test_guard_method_value_is_exempt_after_self() -> None:
    """The first parameter after self is the narrowed one."""
    source = """
class Checker:
    def is_int(self, value) -> TypeGuard[int]: ...
"""
    assert not check_source(source=source, checker=find_pyr403_findings)


def test_guard_classmethod_value_is_exempt_after_cls() -> None:
    """The first parameter after cls is the narrowed one."""
    source = """
class Checker:
    @classmethod
    def is_int(cls, value, strict) -> TypeIs[int]: ...
"""
    assert len(check_source(source=source, checker=find_pyr402_findings)) == 1


def test_guard_staticmethod_value_is_exempt() -> None:
    """A staticmethod has no self, so its first parameter is the narrowed one."""
    source = """
class Checker:
    @staticmethod
    def is_int(value) -> TypeGuard[int]: ...
"""
    assert not check_source(source=source, checker=find_pyr403_findings)


def test_guard_positional_only_value_is_exempt() -> None:
    """A positional-only narrowed value is exempt like any other first positional."""
    source = "def is_int(value, /) -> TypeGuard[int]: ..."

    assert not check_source(source=source, checker=find_pyr403_findings)


def test_async_guard_value_is_exempt() -> None:
    """An async def with a guard annotation is treated like a plain function."""
    source = "async def is_int(value) -> TypeGuard[int]: ..."

    assert not check_source(source=source, checker=find_pyr403_findings)


def test_guard_without_parameters_is_not_flagged() -> None:
    """A guard with no parameters has nothing to exempt and nothing to flag."""
    source = "def is_int() -> TypeGuard[int]: ..."

    assert not check_source(source=source, checker=find_pyr402_findings)
    assert not check_source(source=source, checker=find_pyr403_findings)


def test_guard_with_only_keyword_only_parameter_is_not_flagged() -> None:
    """A guard whose only parameter is keyword-only is not flagged."""
    source = "def is_int(*, value) -> TypeGuard[int]: ..."

    assert not check_source(source=source, checker=find_pyr403_findings)


@pytest.mark.parametrize(
    "preamble",
    ["from other_library import TypeGuard", "class TypeGuard: ...", "import typing\ntyping = None"],
    ids=["imported-from-elsewhere", "defined-locally", "typing-rebound"],
)
def test_recognition_is_by_name_alone_so_shadowed_names_are_still_guards(*, preamble: str) -> None:
    """Shadowing is partial: the exemption follows the spelling and does not resolve what the name refers to."""
    source = f"{preamble}\n\n\ndef is_int(value) -> TypeGuard[int]: ...\n"

    assert not check_source(source=source, checker=find_pyr403_findings)


def test_guard_value_with_default_is_exempt() -> None:
    """A default on the narrowed value does not change the exemption."""
    source = "def is_int(value=None) -> TypeGuard[int]: ..."

    assert not check_source(source=source, checker=find_pyr403_findings)


@pytest.mark.parametrize("parameters", ["value, *args", "*args", "value, **kwargs", "value, *args, **kwargs"])
def test_guard_with_variadic_parameters_is_not_flagged(*, parameters: str) -> None:
    """Variadic parameters are not counted, so the narrowed value stays the only parameter."""
    source = f"def is_int({parameters}) -> TypeGuard[int]: ..."

    assert not check_source(source=source, checker=find_pyr402_findings)
    assert not check_source(source=source, checker=find_pyr403_findings)


def test_guard_with_positional_only_value_and_further_positional_is_flagged_by_pyr402() -> None:
    """A positional parameter after a positional-only guard value still receives PYR402."""
    source = "def is_int(value, /, strict) -> TypeGuard[int]: ..."

    assert len(check_source(source=source, checker=find_pyr402_findings)) == 1
    assert not check_source(source=source, checker=find_pyr403_findings)


def test_each_of_two_guards_is_judged_on_its_own_signature() -> None:
    """Two guards in one file produce one finding only for the one with a further positional parameter."""
    source = """
def first(value) -> TypeGuard[int]: ...
def second(value, strict) -> TypeIs[int]: ...
"""
    findings = check_source(source=source, checker=find_pyr402_findings)

    assert len(findings) == 1
    assert findings[0].message.startswith("Function 'second' ")
