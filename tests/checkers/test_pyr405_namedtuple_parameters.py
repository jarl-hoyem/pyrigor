"""Tests for the PYR405 checker (NamedTuple parameters)."""
# test assertions compare against expected literal values by design,
# not a magic-value problem

# noinspection PyProtectedMember
from pyrigor.checkers.pyr405_namedtuple_parameters import find_findings
from pyrigor.rules import Rule
from tests.checker_helpers import check_source


def test_flags_function_with_bare_tuple_parameter() -> None:
    """A function with a parameter typed as a bare multi-value tuple should be flagged."""
    source = """
def step_bot(*, action: tuple[int, int]) -> None:
    ...
"""
    findings = check_source(source=source, checker=find_findings)

    assert len(findings) == 1
    assert findings[0].message.startswith("Function 'step_bot' ")
    assert findings[0].code is Rule.PYR405


def test_no_finding_for_normal_parameters() -> None:
    """A function with ordinary, non-tuple parameter types should not be flagged."""
    source = """
def step_bot(*, row: int, col: int) -> None:
    ...
"""
    findings = check_source(source=source, checker=find_findings)

    assert not findings


def test_flags_positional_only_tuple_parameter() -> None:
    """A positional-only parameter typed as a bare multi-value tuple should still be flagged."""
    source = """
def step_bot(action: tuple[int, int], /) -> None:
    ...
"""
    findings = check_source(source=source, checker=find_findings)

    assert len(findings) == 1


def test_flags_async_function_with_bare_tuple_parameter() -> None:
    """An async function with a bare-tuple parameter should still be flagged."""
    source = """
async def step_bot(*, action: tuple[int, int]) -> None:
    ...
"""
    findings = check_source(source=source, checker=find_findings)

    assert len(findings) == 1


def test_no_finding_for_single_element_tuple_parameter() -> None:
    """A parameter typed as tuple[X] with only one element is not a multi-value tuple."""
    source = """
def wrap_value(*, value: tuple[int]) -> None:
    ...
"""
    findings = check_source(source=source, checker=find_findings)

    assert not findings


def test_flags_method_with_bare_tuple_parameter_alongside_self() -> None:
    """A method with self (unannotated) plus a bare-tuple parameter should still be flagged, on the real finding."""
    source = """
class Bot:
    def step(self, *, action: tuple[int, int]) -> None:
        ...
"""
    findings = check_source(source=source, checker=find_findings)

    assert len(findings) == 1
    assert findings[0].message.startswith("Function 'step' ")
