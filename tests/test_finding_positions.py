"""Tests for finding positions.

They cover the position index and the spans make_span builds from real source code.
"""

import ast
from itertools import accumulate
from typing import NamedTuple, cast

import pytest
from diagnostics_v2_support import FILE_NAME, Json, load_v2_schema

from pyrigor.findings import (
    BYTE_ORDER_MARK,
    LINE_BREAK,
    ColumnNumber,
    LineNumber,
    Position,
    PositionIndex,
    Span,
    make_span,
)

_POSITION_EXAMPLES = cast("list[Json]", load_v2_schema()["x-span-position-examples"])
_CRLF_TEXT = "\r\n"
_CALL_TEXT = b"apply(1)"
_MULTI_LINE_CALL_TEXT = b"apply(\r\n    1,\r\n)"
_LINES_WITH_EACH_BREAK = b"x\r\nyy\rz"
_MIXED_SOURCE = "\ufeffx = 'a\u2028b\u00e9'\r\ndef apply(left):\r    return '\u20ac\U0001f600'\n\tpass\f\n".encode()

# Characters str.splitlines() treats as line breaks although Python's parser does not.
_NON_BREAKING_SPLITLINES_CHARACTERS = {
    "line-separator": chr(0x2028),
    "paragraph-separator": chr(0x2029),
    "line-tabulation": chr(0x0B),
    "form-feed": chr(0x0C),
    "file-separator": chr(0x1C),
    "group-separator": chr(0x1D),
    "record-separator": chr(0x1E),
    "next-line": chr(0x85),
}


class _CallPosition(NamedTuple):
    """Where the call apply(1) is expected to start in a source."""

    source: bytes
    byte_start: int
    line: int
    column: int


def _call_span(*, source: bytes) -> Span:
    """Build the span of the first call in a source.

    The source is parsed the way the command line interface reads a file.
    """
    tree = ast.parse(source.decode("utf-8-sig"))
    node = next(node for node in ast.walk(tree) if isinstance(node, ast.Call))
    return make_span(node=node, index=PositionIndex(raw=source), file_name=FILE_NAME)


def _body_start(*, raw: bytes) -> int:
    """Return the offset just after a byte-order mark, or 0 without one."""
    return len(BYTE_ORDER_MARK) if raw.startswith(BYTE_ORDER_MARK) else 0


def _reference_position(*, raw: bytes, offset: int) -> Position:
    """Compute a position by splitting the bytes before an offset into lines.

    The index search line starts instead, so the two computations stay independent.
    """
    body_start = _body_start(raw=raw)
    lines = LINE_BREAK.split(raw[body_start:offset])
    return Position(line=LineNumber(len(lines)), column=ColumnNumber(len(lines[-1].decode("utf-8")) + 1))


def _valid_offsets(*, raw: bytes) -> list[int]:
    """List the offset of every character and of the end, except the offset between a CR and its LF."""
    body_start = _body_start(raw=raw)
    text = raw[body_start:].decode()
    offsets = accumulate((len(character.encode()) for character in text), initial=body_start)
    neighbours = zip(offsets, ("", *text), (*text, ""), strict=True)
    return [offset for offset, before, after in neighbours if before + after != _CRLF_TEXT]


@pytest.mark.parametrize("example", _POSITION_EXAMPLES, ids=lambda example: example["name"])
def test_worked_position_example(*, example: Json) -> None:
    """Every worked example in the schema holds verbatim for the position index."""
    raw = cast("str", example["source"]).encode()
    index = PositionIndex(raw=raw)

    start, end = cast("int", example["byte_start"]), cast("int", example["byte_end"])

    assert raw[start:end] == cast("str", example["text"]).encode()
    assert index.position(offset=example["byte_start"]) == (example["line_start"], example["column_start"])
    assert index.position(offset=example["byte_end"]) == (example["line_end"], example["column_end"])


def test_every_valid_offset_matches_reference_computation() -> None:
    """Every position matches the reference computation.

    The source mixes a byte-order mark, all three line breaks and multibyte characters.
    """
    index = PositionIndex(raw=_MIXED_SOURCE)
    valid_offsets = _valid_offsets(raw=_MIXED_SOURCE)

    positions = [index.position(offset=offset) for offset in valid_offsets]

    assert positions == [_reference_position(raw=_MIXED_SOURCE, offset=offset) for offset in valid_offsets]


@pytest.mark.parametrize(
    "character", _NON_BREAKING_SPLITLINES_CHARACTERS.values(), ids=_NON_BREAKING_SPLITLINES_CHARACTERS.keys()
)
def test_splitlines_break_in_string_above_node_is_not_a_line_break(*, character: str) -> None:
    """A break only str.splitlines() recognises leaves the node's position unchanged.

    Its line and its byte offsets both stay as they are without the character.
    """
    first_line = f"x = 'a{character}b'\n".encode()

    span = _call_span(source=first_line + _CALL_TEXT + b"\n")

    assert (span.byte_start, span.byte_end) == (len(first_line), len(first_line) + len(_CALL_TEXT))
    assert (span.line_start, span.column_start, span.line_end, span.column_end) == (2, 1, 2, 9)


@pytest.mark.parametrize(
    "expected",
    [
        pytest.param(_CallPosition(source=BYTE_ORDER_MARK + b"apply(1)\n", byte_start=3, line=1, column=1), id="bom"),
        pytest.param(_CallPosition(source=b"x = 1\r\napply(1)\r\n", byte_start=7, line=2, column=1), id="crlf"),
        pytest.param(_CallPosition(source=b"x = 1\rapply(1)\r", byte_start=6, line=2, column=1), id="lone-cr"),
        pytest.param(
            _CallPosition(source="s = '\u00e9'; apply(1)\n".encode(), byte_start=10, line=1, column=10), id="2-byte"
        ),
        pytest.param(
            _CallPosition(source="s = '\u20ac'; apply(1)\n".encode(), byte_start=11, line=1, column=10), id="3-byte"
        ),
        pytest.param(
            _CallPosition(source="s = '\U0001f600'; apply(1)\n".encode(), byte_start=12, line=1, column=10), id="4-byte"
        ),
        pytest.param(_CallPosition(source=b"if x:\n\tapply(1)\n", byte_start=7, line=2, column=2), id="tab"),
    ],
)
def test_call_span_position(*, expected: _CallPosition) -> None:
    """A single-line call starts where its bytes are, with the column counted in code points."""
    span = _call_span(source=expected.source)

    start, end = span.byte_start, span.byte_end

    assert expected.source[start:end] == _CALL_TEXT
    assert (span.byte_start, span.line_start, span.column_start) == (
        expected.byte_start,
        expected.line,
        expected.column,
    )
    assert (span.line_end, span.column_end) == (expected.line, expected.column + len(_CALL_TEXT))


def test_crlf_inside_multi_line_span() -> None:
    """A span across CRLF breaks covers the breaks in its bytes and ends on its last line."""
    source = b"x = 1\r\n" + _MULTI_LINE_CALL_TEXT + b"\r\n"

    span = _call_span(source=source)

    start, end = span.byte_start, span.byte_end

    assert source[start:end] == _MULTI_LINE_CALL_TEXT
    assert (span.line_start, span.column_start, span.line_end, span.column_end) == (2, 1, 4, 2)


def test_span_ending_at_end_of_line() -> None:
    """A span ending just before a line break ends on that line, after its last character."""
    span = _call_span(source=_CALL_TEXT + b"\nx = 2\n")

    assert (span.byte_end, span.line_end, span.column_end) == (len(_CALL_TEXT), 1, 9)


def test_span_ending_at_end_of_file_without_final_line_break() -> None:
    """A span ending at the end of a file without a final break ends at the file's byte length."""
    source = b"x = 1\n" + _CALL_TEXT

    span = _call_span(source=source)

    assert (span.byte_end, span.line_end, span.column_end) == (len(source), 2, 9)


def test_empty_file_has_one_position() -> None:
    """The only position in an empty file is line 1, column 1."""
    assert PositionIndex(raw=b"").position(offset=0) == (1, 1)


@pytest.mark.parametrize(
    "offset",
    [
        pytest.param(-1, id="negative"),
        pytest.param(0, id="before-byte-order-mark"),
        pytest.param(2, id="inside-byte-order-mark"),
        pytest.param(len(_MIXED_SOURCE) + 1, id="past-end"),
    ],
)
def test_offset_outside_file_body_is_rejected(*, offset: int) -> None:
    """A position lies within the file and not inside its byte-order mark."""
    with pytest.raises(ValueError, match=r"^offset -?[0-9]+ is outside the file or inside its byte-order mark$"):
        PositionIndex(raw=_MIXED_SOURCE).position(offset=offset)


def test_offset_inside_utf8_character_is_rejected() -> None:
    """A position falls on a code-point boundary."""
    with pytest.raises(ValueError, match=r"^offset 1 is inside a UTF-8 character$"):
        PositionIndex(raw="\u20ac".encode()).position(offset=1)


def test_offset_inside_crlf_is_rejected() -> None:
    """No position falls between the carriage return and the line feed of a CRLF."""
    with pytest.raises(ValueError, match=r"^offset 2 is inside a CRLF$"):
        PositionIndex(raw=b"x\r\ny").position(offset=2)


@pytest.mark.parametrize(
    ("line", "utf8_column"),
    [
        pytest.param(0, 0, id="line-zero"),
        pytest.param(4, 0, id="line-past-end"),
        pytest.param(1, -1, id="negative-column"),
        pytest.param(1, 2, id="column-in-crlf"),
        pytest.param(2, 3, id="column-in-lone-cr"),
        pytest.param(3, 2, id="column-past-last-line"),
    ],
)
def test_ast_position_outside_its_line_is_rejected(*, line: int, utf8_column: int) -> None:
    """An ast position that lies outside its own line's content cannot be turned into a byte offset."""
    with pytest.raises(ValueError, match=r"^(line [0-9]+ is outside the file|column -?[0-9]+ is outside line [0-9]+)$"):
        PositionIndex(raw=_LINES_WITH_EACH_BREAK).byte_offset(line=line, utf8_column=utf8_column)


@pytest.mark.parametrize(
    ("line", "utf8_column", "offset"),
    [
        pytest.param(1, 1, 1, id="end-of-crlf-line"),
        pytest.param(2, 2, 5, id="end-of-lone-cr-line"),
        pytest.param(3, 1, 7, id="end-of-file"),
    ],
)
def test_ast_position_at_end_of_line_is_accepted(*, line: int, utf8_column: int, offset: int) -> None:
    """The position just before a line break, or at the end of the file, has a byte offset."""
    index = PositionIndex(raw=_LINES_WITH_EACH_BREAK)

    assert index.byte_offset(line=line, utf8_column=utf8_column) == offset


def test_ast_position_on_first_line_counts_byte_order_mark() -> None:
    """The byte offset of an ast position on line 1 includes the byte-order mark the parser never saw."""
    index = PositionIndex(raw=BYTE_ORDER_MARK + b"x\n")

    assert index.byte_offset(line=1, utf8_column=1) == len(BYTE_ORDER_MARK) + 1


@pytest.mark.parametrize(
    "node",
    [
        pytest.param(ast.Name(id="apply", lineno=1, col_offset=0), id="no-end"),
        pytest.param(ast.Name(id="apply", lineno=1, col_offset=0, end_lineno=1), id="no-end-column"),
        pytest.param(ast.Name(id="apply", lineno=1, col_offset=0, end_col_offset=5), id="no-end-line"),
    ],
)
def test_node_without_end_position_is_rejected(*, node: ast.Name) -> None:
    """A span needs both ends, so a node missing either end field cannot become one."""
    with pytest.raises(ValueError, match=r"^node has no end position$"):
        make_span(node=node, index=PositionIndex(raw=b"apply\n"), file_name=FILE_NAME)
