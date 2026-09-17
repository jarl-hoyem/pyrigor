"""Canonical finding types, their source positions and their v2 JSON form.

The output contract is schemas/pyrigor-diagnostics-v2.json. The types reject the structural mistakes a finding can be
built with and the invariants the schema cannot express. The schema checks everything else when a serialised finding
is validated, so its patterns are not repeated here.
"""

import ast
import re
import unicodedata
from bisect import bisect_right
from dataclasses import dataclass
from enum import Enum
from itertools import pairwise
from typing import Final, NamedTuple, NewType

from pyrigor.rules import Rule, Severity

FileName = NewType("FileName", str)
ByteOffset = NewType("ByteOffset", int)
LineNumber = NewType("LineNumber", int)
ColumnNumber = NewType("ColumnNumber", int)
JsonObject = dict[str, object]

_LOCALS_SEGMENT = "<locals>"
# Annotated, because PyCharm infers a byte literal read from another file as str, codecs.BOM_UTF8 included.
BYTE_ORDER_MARK: Final[bytes] = b"\xef\xbb\xbf"
# Where Python's parser ends a line. Other characters str.splitlines() treats as breaks, such as U+2028, do not.
LINE_BREAK = re.compile(rb"\r\n|\r|\n")
_CRLF = b"\r\n"
_LONE_SURROGATE = re.compile("[\\ud800-\\udfff]")
_CONTINUATION_BYTE_MASK = 0b1100_0000
_CONTINUATION_BYTE_BITS = 0b1000_0000


class Applicability(Enum):
    """Whether a fix may be applied automatically, in Ruff's terminology."""

    SAFE = "safe"
    UNSAFE = "unsafe"
    DISPLAY = "display"


class SymbolKind(Enum):
    """The kind of definition that encloses a finding."""

    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    MODULE = "module"


class Position(NamedTuple):
    """A 1-based line and a 1-based column counted in code points."""

    line: LineNumber
    column: ColumnNumber


def _require(*, condition: bool, message: str) -> None:
    """Raise a ValueError with the message unless the condition holds.

    Args:
        condition: The invariant that must hold.
        message: What is wrong when it does not.

    Raises:
        ValueError: If the condition is false.
    """
    if not condition:
        raise ValueError(message)


def _require_valid_unicode(*, text: str, field: str) -> None:
    """Reject a string that cannot be encoded as UTF-8.

    Args:
        text: The string to check.
        field: The field name for the error message.
    """
    _require(condition=_LONE_SURROGATE.search(text) is None, message=f"{field} contains a lone surrogate")


def _require_file_name(*, file_name: FileName) -> None:
    """Reject a file name that is not valid Unicode in normalisation form NFC.

    Args:
        file_name: The file name to check.
    """
    _require_valid_unicode(text=file_name, field="file_name")
    _require(
        condition=unicodedata.is_normalized("NFC", file_name),
        message="file_name is not in Unicode normalisation form NFC",
    )


def _require_byte_range(*, byte_start: ByteOffset, byte_end: ByteOffset) -> None:
    """Reject a byte range that ends before it starts.

    Args:
        byte_start: The first byte of the range.
        byte_end: The byte after the range.
    """
    _require(condition=byte_start <= byte_end, message="byte_start is after byte_end")


@dataclass(frozen=True, slots=True, kw_only=True)
class Span:  # pylint: disable=too-many-instance-attributes # the v2 schema fixes these nine fields
    """A source range. Build one with make_span."""

    file_name: FileName
    byte_start: ByteOffset
    byte_end: ByteOffset
    line_start: LineNumber
    column_start: ColumnNumber
    line_end: LineNumber
    column_end: ColumnNumber
    is_primary: bool
    label: str | None = None

    def __post_init__(self) -> None:
        """Reject a span that ends before it starts or holds text that is not valid Unicode."""
        _require_file_name(file_name=self.file_name)
        _require_byte_range(byte_start=self.byte_start, byte_end=self.byte_end)
        on_one_line = self.line_start == self.line_end
        _require(
            condition=self.line_start < self.line_end or (on_one_line and self.column_start <= self.column_end),
            message="start position is after its end position",
        )
        if self.label is not None:
            _require_valid_unicode(text=self.label, field="label")


def _is_qualified_name(*, name: str) -> bool:
    """Return whether every segment of a name is an identifier, with <locals> only between two identifiers.

    Args:
        name: The dotted name to check.

    Returns:
        True if the name has the shape of a Python __qualname__.
    """
    return all(segment.isidentifier() for segment in name.replace(f".{_LOCALS_SEGMENT}.", ".").split("."))


@dataclass(frozen=True, slots=True, kw_only=True)
class EnclosingSymbol:
    """The innermost function, method or class that contains a finding, or its module."""

    kind: SymbolKind
    name: str

    def __post_init__(self) -> None:
        """Reject a function, method or class name that is not a Python __qualname__."""
        _require_valid_unicode(text=self.name, field="name")
        _require(
            condition=self.kind is SymbolKind.MODULE or _is_qualified_name(name=self.name),
            message=f"name {self.name!r} is not a Python __qualname__",
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Edit:
    """Replaces a byte range of the original file with content."""

    file_name: FileName
    byte_start: ByteOffset
    byte_end: ByteOffset
    content: str

    def __post_init__(self) -> None:
        """Reject an edit that ends before it starts or holds text that is not valid Unicode."""
        _require_file_name(file_name=self.file_name)
        _require_byte_range(byte_start=self.byte_start, byte_end=self.byte_end)
        _require_valid_unicode(text=self.content, field="content")


def _require_edit_follows(*, previous: Edit, current: Edit) -> None:
    """Reject an edit that is not sorted after the previous one, repeats its range or overlaps it.

    Args:
        previous: The earlier edit in the fix.
        current: The edit after it.
    """
    previous_range = (previous.byte_start, previous.byte_end)
    current_range = (current.byte_start, current.byte_end)
    _require(condition=previous_range <= current_range, message="edits are not sorted")
    _require(condition=previous_range != current_range, message="edits share a range")
    _require(condition=previous.byte_end <= current.byte_start, message="edits overlap")


@dataclass(frozen=True, slots=True, kw_only=True)
class Fix:
    """One way to resolve a finding, as edits that apply together."""

    applicability: Applicability
    message: str
    edits: tuple[Edit, ...]

    def __post_init__(self) -> None:
        """Reject a fix without edits, with edits in several files or with unsorted or overlapping edits."""
        _require_valid_unicode(text=self.message, field="message")
        _require(condition=bool(self.edits), message="a fix needs at least one edit")
        _require(
            condition=len({edit.file_name for edit in self.edits}) == 1,
            message="edits of one fix are in different files",
        )
        for previous, current in pairwise(self.edits):
            _require_edit_follows(previous=previous, current=current)


@dataclass(frozen=True, slots=True, kw_only=True)
class Finding:
    """One concrete occurrence of a rule violation."""

    code: Rule
    message: str
    spans: tuple[Span, ...]
    enclosing_symbol: EnclosingSymbol | None = None
    fixes: tuple[Fix, ...]

    def __post_init__(self) -> None:
        """Reject a finding without exactly one primary span or with a repeated span or fix."""
        _require_valid_unicode(text=self.message, field="message")
        _require(condition=bool(self.spans), message="a finding needs at least one span")
        _require(
            condition=sum(span.is_primary for span in self.spans) == 1,
            message="a finding needs exactly one primary span",
        )
        _require(condition=len(set(self.spans)) == len(self.spans), message="spans repeat")
        _require(condition=len(set(self.fixes)) == len(self.fixes), message="fixes repeat")

    @property
    def level(self) -> Severity:
        """The severity pyrigor assigns to the rule, so it cannot disagree with the code."""
        return self.code.severity


class PositionIndex:
    """The line starts of one file's raw bytes, found once so that each position is a lookup."""

    __slots__ = ("_line_starts", "_raw")

    def __init__(self, *, raw: bytes) -> None:
        """Index the raw bytes of a UTF-8 file.

        Args:
            raw: The file's bytes, exactly as read from disk.
        """
        body_start = len(BYTE_ORDER_MARK) if raw.startswith(BYTE_ORDER_MARK) else 0
        self._raw = raw
        self._line_starts = (body_start, *(match.end() for match in LINE_BREAK.finditer(raw)))

    def _content_end(self, *, line_index: int) -> int:
        """Find the offset of a line's break, or the end of the file for the last line.

        Args:
            line_index: The 0-based line.

        Returns:
            The offset just after the line's last character.
        """
        if line_index == len(self._line_starts) - 1:
            return len(self._raw)
        next_start = self._line_starts[line_index + 1]
        break_start = next_start - len(_CRLF)
        break_length = len(_CRLF) if self._raw[break_start:next_start] == _CRLF else 1
        return next_start - break_length

    def byte_offset(self, *, line: int, utf8_column: int) -> ByteOffset:
        """Turn a line and a UTF-8 column offset, as ast reports them, into a byte offset into the raw file.

        Args:
            line: The 1-based line, as in ast's lineno.
            utf8_column: The 0-based UTF-8 byte offset into the line, as in ast's col_offset.

        Returns:
            The byte offset, which counts a byte-order mark the parser never saw.
        """
        _require(condition=1 <= line <= len(self._line_starts), message=f"line {line} is outside the file")
        offset = self._line_starts[line - 1] + utf8_column
        _require(
            condition=utf8_column >= 0 and offset <= self._content_end(line_index=line - 1),
            message=f"column {utf8_column} is outside line {line}",
        )
        return ByteOffset(offset)

    def position(self, *, offset: int) -> Position:
        """Find the line and code-point column of a byte offset.

        Args:
            offset: A byte offset into the raw file.

        Returns:
            The position, where a line's break characters belong to the line they end.
        """
        raw = self._raw
        _require(
            condition=self._line_starts[0] <= offset <= len(raw),
            message=f"offset {offset} is outside the file or inside its byte-order mark",
        )
        _require(
            condition=offset == len(raw) or raw[offset] & _CONTINUATION_BYTE_MASK != _CONTINUATION_BYTE_BITS,
            message=f"offset {offset} is inside a UTF-8 character",
        )
        before, after = offset - 1, offset + 1
        _require(condition=raw[before:after] != _CRLF, message=f"offset {offset} is inside a CRLF")
        line_index = bisect_right(self._line_starts, offset) - 1
        line_start = self._line_starts[line_index]
        column = len(raw[line_start:offset].decode()) + 1
        return Position(line=LineNumber(line_index + 1), column=ColumnNumber(column))


def make_span(
    *,
    node: ast.stmt | ast.expr | ast.arg,
    index: PositionIndex,
    file_name: FileName,
    is_primary: bool = True,
    label: str | None = None,
) -> Span:
    """Build the span of an ast node, the only way pyrigor constructs a span.

    Args:
        node: The node whose source range the span covers.
        index: The position index of the node's file, built once per file.
        file_name: The file's path is relative to the working directory, with forward slashes.
        is_primary: Whether this is the finding's focal location.
        label: Why this range matters, or None when no explanation is needed.

    Returns:
        The span, with byte offsets into the raw file and code-point columns.

    Raises:
        ValueError: If the node has no end position.
    """
    if node.end_lineno is None or node.end_col_offset is None:
        raise ValueError("node has no end position")
    byte_start = index.byte_offset(line=node.lineno, utf8_column=node.col_offset)
    byte_end = index.byte_offset(line=node.end_lineno, utf8_column=node.end_col_offset)
    start = index.position(offset=byte_start)
    end = index.position(offset=byte_end)
    return Span(
        file_name=file_name,
        byte_start=byte_start,
        byte_end=byte_end,
        line_start=start.line,
        column_start=start.column,
        line_end=end.line,
        column_end=end.column,
        is_primary=is_primary,
        label=label,
    )


def _span_to_json(*, span: Span) -> JsonObject:
    """Serialise a span, omitting an absent label.

    Args:
        span: The span to serialise.

    Returns:
        The span's v2 JSON object.
    """
    result: JsonObject = {
        "file_name": span.file_name,
        "byte_start": span.byte_start,
        "byte_end": span.byte_end,
        "line_start": span.line_start,
        "column_start": span.column_start,
        "line_end": span.line_end,
        "column_end": span.column_end,
        "is_primary": span.is_primary,
    }
    if span.label is not None:
        result["label"] = span.label
    return result


def _fix_to_json(*, fix: Fix) -> JsonObject:
    """Serialise a fix and its edits.

    Args:
        fix: The fix to serialise.

    Returns:
        The fix's v2 JSON object.
    """
    edits = [
        {"file_name": edit.file_name, "byte_start": edit.byte_start, "byte_end": edit.byte_end, "content": edit.content}
        for edit in fix.edits
    ]
    return {"applicability": fix.applicability.value, "message": fix.message, "edits": edits}


def finding_to_json(*, finding: Finding) -> JsonObject:
    """Serialise a finding to its v2 JSON shape, omitting absent optional values and always writing its fixes.

    Args:
        finding: The finding to serialise.

    Returns:
        The finding's v2 JSON object, ready for json.dumps.
    """
    result: JsonObject = {
        "code": finding.code.name,
        "message": finding.message,
        "level": finding.level.value,
        "spans": [_span_to_json(span=span) for span in finding.spans],
    }
    if finding.enclosing_symbol is not None:
        result["enclosing_symbol"] = {
            "kind": finding.enclosing_symbol.kind.value,
            "name": finding.enclosing_symbol.name,
        }
    result["fixes"] = [_fix_to_json(fix=fix) for fix in finding.fixes]
    return result
