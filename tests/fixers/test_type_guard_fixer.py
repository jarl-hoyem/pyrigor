"""Tests that the PYR402 fixer leaves TypeGuard and TypeIs functions alone."""
# test assertions compare against expected literal values by design,
# not a magic-value problem

import pytest

from pyrigor.fixers.pyr402_keyword_only_arguments_fixer import FixStatus, fix_source


@pytest.mark.parametrize("annotation", ["TypeGuard[int]", "TypeIs[int]", "typing.TypeGuard[int]"])
def test_guard_function_with_further_positional_parameter_is_unchanged(*, annotation: str) -> None:
    """A leading bare star would make the narrowed value keyword-only, so nothing is inserted."""
    source = f"def is_int(value, strict) -> {annotation}: ...\n"

    result = fix_source(source=source)

    assert result.status is FixStatus.UNCHANGED
    assert result.source == source


def test_guard_function_with_positional_only_parameter_is_unchanged_not_rejected() -> None:
    """Skipping happens before the positional-only rejection."""
    source = "def is_int(value, /, strict) -> TypeGuard[int]: ...\n"

    result = fix_source(source=source)

    assert result.status is FixStatus.UNCHANGED


@pytest.mark.parametrize(
    "source",
    [
        "class Checker:\n    def is_int(self, value, strict) -> TypeGuard[int]: ...\n",
        "async def is_int(value, strict) -> TypeIs[int]: ...\n",
        "class Checker:\n    @classmethod\n    def is_int(cls, value, strict) -> TypeGuard[int]: ...\n",
    ],
    ids=["method", "async", "classmethod"],
)
def test_guard_method_and_async_forms_are_unchanged(*, source: str) -> None:
    """Methods and async guards are skipped like plain functions."""
    result = fix_source(source=source)

    assert result.status is FixStatus.UNCHANGED
    assert result.source == source


def test_ordinary_function_beside_a_guard_is_still_fixed() -> None:
    """Only the guard is skipped. Other functions in the same source are fixed."""
    guard = "def is_int(value, strict) -> TypeGuard[int]: ...\n\n\n"
    source = guard + "def add(left, right) -> int: ...\n"
    expected = guard + "def add(*, left, right) -> int: ...\n"

    result = fix_source(source=source)

    assert result.status is FixStatus.CHANGED
    assert result.source == expected
