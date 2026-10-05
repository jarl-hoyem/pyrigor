"""Tests for PYR406's reading of quoted return annotations."""

import ast
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pyrigor.checkers import pyr406_return_values_used
from pyrigor.checkers.pyr406_return_values_used import find_findings
from tests.checker_helpers import check_source

_FUTURE_IMPORT = "from __future__ import annotations\n\n"
_PROTECTED = True
_NOT_PROTECTED = False


def _is_flagged(*, annotation: str, header: str = "", keyword: str = "def") -> bool:
    """Check whether PYR406 flags a bare call to a function with the annotation, written as the source says."""
    source = f"{header}{keyword} compute() -> {annotation}:\n    ...\n\n\ncompute()\n"
    return bool(check_source(source=source, checker=find_findings))


@pytest.mark.parametrize(
    ("annotation", "protected"),
    [
        pytest.param("int", _PROTECTED, id="builtin"),
        pytest.param("list[int]", _PROTECTED, id="subscript"),
        pytest.param("dict[str, list[int]]", _PROTECTED, id="nested-subscript"),
        pytest.param("int | str", _PROTECTED, id="union"),
        pytest.param("int | None", _PROTECTED, id="union-with-none"),
        pytest.param("typing.Optional[int]", _PROTECTED, id="attribute-subscript"),
        pytest.param("None", _NOT_PROTECTED, id="none"),
        pytest.param("NoReturn", _NOT_PROTECTED, id="no-return"),
        pytest.param("typing.NoReturn", _NOT_PROTECTED, id="attribute-no-return"),
        pytest.param("Never", _NOT_PROTECTED, id="never"),
        pytest.param("Iterator[int]", _NOT_PROTECTED, id="iterator"),
        pytest.param("Generator[int, None, None]", _NOT_PROTECTED, id="generator"),
        pytest.param("AsyncGenerator[int, None]", _NOT_PROTECTED, id="async-generator"),
        pytest.param("typing.Iterator[int]", _NOT_PROTECTED, id="attribute-iterator"),
    ],
)
def test_a_quoted_annotation_is_judged_like_the_unquoted_one(*, annotation: str, protected: bool) -> None:
    """The same annotation gives the same verdict with and without quotes."""
    unquoted = _is_flagged(annotation=annotation)
    quoted = _is_flagged(annotation=repr(annotation))
    assert (unquoted, quoted) == (protected, protected)


def test_a_quoted_annotation_on_an_async_function_is_flagged() -> None:
    """Quoting works the same on an async function."""
    assert _is_flagged(annotation='"int"', keyword="async def")


@pytest.mark.parametrize("annotation", ["int", '"int"', '"None"'])
def test_the_future_annotations_import_changes_nothing(*, annotation: str) -> None:
    """The import makes annotation strings at runtime, but the tree keeps real expressions, so nothing differs."""
    with_import = _is_flagged(annotation=annotation, header=_FUTURE_IMPORT)
    without_import = _is_flagged(annotation=annotation)
    assert with_import is without_import


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("", id="empty"),
        pytest.param("   ", id="spaces-only"),
        pytest.param(" int", id="leading-space-which-python-rejects-too"),
        pytest.param("not valid python(", id="unbalanced-parenthesis"),
        pytest.param("int int", id="two-names"),
        pytest.param("1 +", id="incomplete-expression"),
        pytest.param("'int'", id="nested-string"),
        pytest.param("None", id="quoted-none"),
        pytest.param("x if y else z", id="conditional-expression"),
        pytest.param("compute(x)", id="call-expression"),
        pytest.param("[int]", id="list-display"),
        pytest.param("int\x00", id="null-byte"),
    ],
)
def test_text_that_names_no_type_is_not_flagged_and_does_not_crash(*, text: str) -> None:
    """Quoted text that is not an expression naming a type leaves the call unflagged and never crashes the run."""
    assert not _is_flagged(annotation=repr(text))


@pytest.mark.parametrize("annotation", ["5", "1.5", "True", "...", 'b"int"'])
def test_a_constant_that_is_not_text_is_not_flagged(*, annotation: str) -> None:
    """A constant annotation other than a string names nothing, and parsing it as text would crash."""
    assert not _is_flagged(annotation=annotation)


@pytest.mark.parametrize("error", [ValueError, RecursionError])
def test_text_that_makes_the_parser_fail_in_another_way_is_not_flagged(
    *, monkeypatch: pytest.MonkeyPatch, error: type[Exception]
) -> None:
    """Python 3.11 raises a ValueError for a null byte and a huge expression a RecursionError, so both are caught."""
    failing_ast = SimpleNamespace(**{**vars(ast), "parse": Mock(side_effect=error("the parser failed"))})
    monkeypatch.setattr(pyr406_return_values_used, "ast", failing_ast)
    assert not _is_flagged(annotation='"int"')
