"""Tests that the PYR402 fixer keeps the guarded parameter of TypeGuard and TypeIs functions positional."""
# test assertions compare against expected literal values by design,
# not a magic-value problem

import ast
from typing import Final

import pytest

from pyrigor.fixers.pyr402_keyword_only_arguments_fixer import FixRejectedError, FixStatus, fix_source

_CASES = [
    ("plain", "def f(value, a) -> TypeGuard[int]: ...\n", "def f(value, *, a) -> TypeGuard[int]: ...\n"),
    ("type-is", "def f(value, a) -> TypeIs[int]: ...\n", "def f(value, *, a) -> TypeIs[int]: ...\n"),
    (
        "typing",
        "def f(value, a) -> typing.TypeGuard[int]: ...\n",
        "def f(value, *, a) -> typing.TypeGuard[int]: ...\n",
    ),
    (
        "typing-extensions",
        "def f(value, a) -> typing_extensions.TypeIs[int]: ...\n",
        "def f(value, *, a) -> typing_extensions.TypeIs[int]: ...\n",
    ),
    (
        "three-parameters",
        "def f(value, a, b) -> TypeGuard[int]: ...\n",
        "def f(value, *, a, b) -> TypeGuard[int]: ...\n",
    ),
    (
        "method",
        "class C:\n    def f(self, value, a) -> TypeGuard[int]: ...\n",
        "class C:\n    def f(self, value, *, a) -> TypeGuard[int]: ...\n",
    ),
    (
        "classmethod",
        "class C:\n    @classmethod\n    def f(cls, value, a) -> TypeGuard[int]: ...\n",
        "class C:\n    @classmethod\n    def f(cls, value, *, a) -> TypeGuard[int]: ...\n",
    ),
    ("async", "async def f(value, a) -> TypeIs[int]: ...\n", "async def f(value, *, a) -> TypeIs[int]: ...\n"),
    (
        "decorated",
        "@decorator\ndef f(value, a) -> TypeGuard[int]: ...\n",
        "@decorator\ndef f(value, *, a) -> TypeGuard[int]: ...\n",
    ),
    (
        "nested",
        "def outer():\n    def f(value, a) -> TypeGuard[int]: ...\n",
        "def outer():\n    def f(value, *, a) -> TypeGuard[int]: ...\n",
    ),
    (
        "annotation-with-comma",
        "def f(value: dict[str, int], a) -> TypeGuard[int]: ...\n",
        "def f(value: dict[str, int], *, a) -> TypeGuard[int]: ...\n",
    ),
    (
        "default-tuple",
        "def f(value=(1, 2), a=3) -> TypeGuard[int]: ...\n",
        "def f(value=(1, 2), *, a=3) -> TypeGuard[int]: ...\n",
    ),
    (
        "default-parenthesised",
        "def f(value=(None), a=1) -> TypeGuard[int]: ...\n",
        "def f(value=(None), *, a=1) -> TypeGuard[int]: ...\n",
    ),
    (
        "default-lambda",
        "def f(value=lambda x, y: 0, a=1) -> TypeGuard[int]: ...\n",
        "def f(value=lambda x, y: 0, *, a=1) -> TypeGuard[int]: ...\n",
    ),
    (
        "default-string-with-comma",
        'def f(value="a,b", a=1) -> TypeGuard[int]: ...\n',
        'def f(value="a,b", *, a=1) -> TypeGuard[int]: ...\n',
    ),
    (
        "non-ascii-default",
        'def f(value="é,", a=1) -> TypeGuard[int]: ...\n',
        'def f(value="é,", *, a=1) -> TypeGuard[int]: ...\n',
    ),
    (
        "non-ascii-before",
        "# é\ndef f(value, a) -> TypeGuard[int]: ...\n",
        "# é\ndef f(value, *, a) -> TypeGuard[int]: ...\n",
    ),
    (
        "wrapped",
        "def f(\n    value,\n    a,\n) -> TypeGuard[int]: ...\n",
        "def f(\n    value, *,\n    a,\n) -> TypeGuard[int]: ...\n",
    ),
    (
        "comment-before-comma",
        "def f(\n    value  # one, two\n    , a\n) -> TypeGuard[int]: ...\n",
        "def f(\n    value  # one, two\n    , *, a\n) -> TypeGuard[int]: ...\n",
    ),
    (
        "comment-after-comma",
        "def f(\n    value,  # note\n    a,\n) -> TypeGuard[int]: ...\n",
        "def f(\n    value, *,  # note\n    a,\n) -> TypeGuard[int]: ...\n",
    ),
    (
        "backslash-continuation",
        "def f(value \\\n    , a) -> TypeGuard[int]: ...\n",
        "def f(value \\\n    , *, a) -> TypeGuard[int]: ...\n",
    ),
]
_IDS = [name for name, _, _ in _CASES]
_PAIRS = [(source, expected) for _, source, expected in _CASES]
_FIXED = [expected for _, _, expected in _CASES]
_FUNCTION_NAME: Final = "f"
_SELF_OR_CLS = {"self", "cls"}


@pytest.mark.parametrize(("source", "expected"), _PAIRS, ids=_IDS)
def test_star_goes_after_the_guarded_parameter(*, source: str, expected: str) -> None:
    """The bare star follows the guarded parameter, whatever its annotation, default or layout."""
    result = fix_source(source=source)

    assert result.status is FixStatus.CHANGED
    assert result.source == expected


def _guard_function(*, source: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """Find the function named f in a source."""
    functions = [
        node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    return next(function for function in functions if function.name == _FUNCTION_NAME)


@pytest.mark.parametrize("fixed", _FIXED, ids=_IDS)
def test_fixed_source_parses_with_the_guarded_value_still_positional(*, fixed: str) -> None:
    """The result is valid Python and the guarded value stays positional."""
    function = _guard_function(source=fixed)
    positional = [argument.arg for argument in function.args.args]

    assert [name for name in positional if name not in _SELF_OR_CLS] == ["value"]
    assert function.args.kwonlyargs


@pytest.mark.parametrize("fixed", _FIXED, ids=_IDS)
def test_fixing_twice_changes_nothing_more(*, fixed: str) -> None:
    """A second run finds nothing left to fix."""
    second = fix_source(source=fixed)

    assert second.status is FixStatus.UNCHANGED
    assert second.source == fixed


def test_crlf_line_endings_are_preserved() -> None:
    """A CRLF file keeps its line breaks around the insertion."""
    result = fix_source(source="def f(\r\n    value,\r\n    a,\r\n) -> TypeGuard[int]: ...\r\n")

    expected = "def f(\r\n    value, *,\r\n    a,\r\n) -> TypeGuard[int]: ...\r\n"
    assert result.source == expected


def test_a_comment_ends_at_a_lone_carriage_return() -> None:
    """A bare carriage return is a line break in Python, so it ends a comment holding a comma."""
    result = fix_source(source="def f(\r    value  # one, two\r    , a\r) -> TypeGuard[int]: ...\r")

    expected = "def f(\r    value  # one, two\r    , *, a\r) -> TypeGuard[int]: ...\r"
    assert result.source == expected


def test_bytes_with_a_byte_order_mark_are_fixed_and_returned_as_bytes() -> None:
    """Byte input with a BOM and non-ASCII text stays bytes and keeps the BOM."""
    source = "\ufeff# é\ndef f(value, a) -> TypeGuard[int]: ...\n".encode()

    result = fix_source(source=source)

    assert result.source == "\ufeff# é\ndef f(value, *, a) -> TypeGuard[int]: ...\n".encode()


def test_dry_run_reports_the_change_without_applying_it() -> None:
    """A dry run reports a pending change and returns the original source."""
    source = "def f(value, a) -> TypeGuard[int]: ...\n"

    result = fix_source(source=source, dry_run=True)

    assert result.status is FixStatus.WOULD_CHANGE
    assert result.source == source


def test_positional_only_guard_is_rejected() -> None:
    """A positional-only guarded value keeps the existing rejection."""
    with pytest.raises(FixRejectedError):
        fix_source(source="def f(value, /, a) -> TypeGuard[int]: ...\n")


@pytest.mark.parametrize(
    "source",
    [
        "def f(value, a, *args) -> TypeGuard[int]: ...\n",
        "def f(value) -> TypeGuard[int]: ...\n",
        "def f(value, *, a) -> TypeGuard[int]: ...\n",
    ],
    ids=["varargs", "lone-parameter", "already-keyword-only"],
)
def test_guards_with_nothing_to_fix_are_unchanged(*, source: str) -> None:
    """Variadic, single-parameter and already-correct guards are left alone."""
    result = fix_source(source=source)

    assert result.status is FixStatus.UNCHANGED
    assert result.source == source


def test_a_guard_and_an_ordinary_function_are_both_fixed() -> None:
    """Both functions in one source receive their own insertion."""
    result = fix_source(source="def f(value, a) -> TypeGuard[int]: ...\n\n\ndef add(left, right): ...\n")

    expected = "def f(value, *, a) -> TypeGuard[int]: ...\n\n\ndef add(*, left, right): ...\n"
    assert result.source == expected
