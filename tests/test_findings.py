"""Tests for the canonical finding types: their schema shape, their invariants and their v2 JSON form."""

import ast
import dataclasses
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple, TypeVar, cast

import pytest
from diagnostics_v2_support import FILE_NAME, REPOSITORY_ROOT, Json, definition_validator, load_v2_schema

from pyrigor.findings import (
    Applicability,
    ByteOffset,
    ColumnNumber,
    Edit,
    EnclosingSymbol,
    FileName,
    Finding,
    Fix,
    LineNumber,
    PositionIndex,
    Span,
    SymbolKind,
    finding_to_json,
    make_span,
)
from pyrigor.rules import Rule, Severity

FindingType = type[Finding | Span | EnclosingSymbol | Fix | Edit]
_NodeT = TypeVar("_NodeT", bound=ast.AST)

_DEFINITIONS = cast("Json", load_v2_schema()["$defs"])
_SPAN_CONSTRUCTOR = Span.__name__
_METHOD_SOURCE = b"class Store:\n    def save(self, item, target):\n        return copy(item, target)\n"
_CALL_TEXT = b"copy(item, target)"
_KEYWORD_CALL_TEXT = b"copy(item=item, target=target)"
_PARAMETERS_TEXT = b"(self, item, target)"
_KEYWORD_PARAMETERS_TEXT = b"(self, *, item, target)"
_LONE_SURROGATE = chr(0xD800)
_DECOMPOSED_FILE_NAME = FileName("src/e" + chr(0x0301) + ".py")
_COMPOSED_FILE_NAME = FileName("src/" + chr(0xE9) + ".py")

_SPAN = Span(
    file_name=FILE_NAME,
    byte_start=ByteOffset(4),
    byte_end=ByteOffset(9),
    line_start=LineNumber(1),
    column_start=ColumnNumber(5),
    line_end=LineNumber(1),
    column_end=ColumnNumber(10),
    is_primary=True,
)
_EDIT = Edit(file_name=FILE_NAME, byte_start=ByteOffset(0), byte_end=ByteOffset(1), content="x")
_FIX = Fix(applicability=Applicability.SAFE, message="Apply the change", edits=(_EDIT,))
_FINDING = Finding(code=Rule.PYR402, message="Positional parameters", spans=(_SPAN,), fixes=())


class _TypeDefinition(NamedTuple):
    """A Python finding type and the schema definition it implements."""

    python_type: FindingType
    definition: str
    derived: frozenset[str] = frozenset()


_TYPE_DEFINITIONS = (
    _TypeDefinition(python_type=Finding, definition="Finding", derived=frozenset({"level"})),
    _TypeDefinition(python_type=Span, definition="Span"),
    _TypeDefinition(python_type=EnclosingSymbol, definition="EnclosingSymbol"),
    _TypeDefinition(python_type=Fix, definition="Fix"),
    _TypeDefinition(python_type=Edit, definition="Edit"),
)


def _serialised(*, finding: Finding) -> Json:
    """Serialise a finding and check that it validates against the schema's Finding definition."""
    # mypy and pyright need the cast, because a dict of objects is not a JSON argument for jsonschema
    # noinspection PyUnnecessaryCast
    document = cast("Json", finding_to_json(finding=finding))
    errors = [error.message for error in definition_validator(definition="Finding").iter_errors(document)]
    assert not errors
    return document


def _edit(*, byte_start: int, byte_end: int) -> Edit:
    """Build an edit of a byte range."""
    return dataclasses.replace(_EDIT, byte_start=ByteOffset(byte_start), byte_end=ByteOffset(byte_end))


def _edits(*ranges: tuple[int, int]) -> tuple[Edit, ...]:
    """Build edits of byte ranges, in the order given."""
    return tuple(_edit(byte_start=start, byte_end=end) for start, end in ranges)


def _first_node(*, node_type: type[_NodeT]) -> _NodeT:
    """Return the first node of a type in the method source."""
    return next(node for node in ast.walk(ast.parse(_METHOD_SOURCE)) if isinstance(node, node_type))


def _argument_edit(*, argument: ast.expr, index: PositionIndex) -> Edit:
    """Build an edit that passes a name argument by keyword."""
    span = make_span(node=argument, index=index, file_name=FILE_NAME)
    name = ast.unparse(argument)
    return Edit(file_name=FILE_NAME, byte_start=span.byte_start, byte_end=span.byte_end, content=f"{name}={name}")


def _method_finding() -> Finding:
    """Build a finding from real source code.

    It has labelled spans, an enclosing symbol and two alternative fixes.
    """
    index = PositionIndex(raw=_METHOD_SOURCE)
    function = _first_node(node_type=ast.FunctionDef)
    call = _first_node(node_type=ast.Call)
    keyword_start = make_span(node=function.args.args[1], index=index, file_name=FILE_NAME).byte_start
    keyword_edit = Edit(file_name=FILE_NAME, byte_start=keyword_start, byte_end=keyword_start, content="*, ")
    call_edits = tuple(_argument_edit(argument=argument, index=index) for argument in call.args)
    return Finding(
        code=Rule.PYR402,
        message="save has positional parameters",
        spans=(
            make_span(node=function, index=index, file_name=FILE_NAME, label="defined here"),
            make_span(node=call, index=index, file_name=FILE_NAME, is_primary=False, label="called here"),
        ),
        enclosing_symbol=EnclosingSymbol(kind=SymbolKind.METHOD, name="Store.save"),
        fixes=(
            Fix(applicability=Applicability.SAFE, message="Make the parameters keyword-only", edits=(keyword_edit,)),
            Fix(applicability=Applicability.UNSAFE, message="Pass the arguments by keyword", edits=call_edits),
        ),
    )


def _applied(*, fix: Fix) -> bytes:
    """Apply a fix to the method source, last edit first.

    The earlier offsets then still refer to the original.
    """
    edited = _METHOD_SOURCE
    for edit in reversed(fix.edits):
        start, end = edit.byte_start, edit.byte_end
        edited = edited[:start] + edit.content.encode() + edited[end:]
    return edited


def _called_name(*, call: ast.Call) -> str | None:
    """Return the name a call calls, whether bare or as an attribute, or None for any other callee."""
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return call.func.id if isinstance(call.func, ast.Name) else None


def _called_names(*, path: Path) -> set[str | None]:
    """Collect the name of the function or method that each call in a Python file calls."""
    tree = ast.parse(path.read_text("utf-8"))
    return {_called_name(call=node) for node in ast.walk(tree) if isinstance(node, ast.Call)}


@pytest.mark.parametrize("type_definition", _TYPE_DEFINITIONS, ids=lambda pair: pair.definition)
def test_type_properties_match_schema_definition(*, type_definition: _TypeDefinition) -> None:
    """Each type has the schema definition's properties, and exactly its required ones have no default."""
    schema = cast("Json", _DEFINITIONS[type_definition.definition])
    fields = dataclasses.fields(type_definition.python_type)
    required = {field.name for field in fields if field.default is dataclasses.MISSING}

    assert {field.name for field in fields} | type_definition.derived == set(cast("Json", schema["properties"]))
    assert required | type_definition.derived == set(cast("list[str]", schema["required"]))


def test_derived_properties_exist() -> None:
    """Finding computes level as a property, because the schema requires the field."""
    assert isinstance(Finding.level, property)


def test_enum_values_match_schema() -> None:
    """The level, applicability and kind enums hold the schema's values, in order."""
    assert [severity.value for severity in Severity] == _DEFINITIONS["Finding"]["properties"]["level"]["enum"]
    assert [value.value for value in Applicability] == _DEFINITIONS["Fix"]["properties"]["applicability"]["enum"]
    assert [kind.value for kind in SymbolKind] == _DEFINITIONS["EnclosingSymbol"]["properties"]["kind"]["enum"]


def test_finding_level_is_rule_severity() -> None:
    """A finding's level is the severity of its rule, so the two cannot disagree."""
    finding = dataclasses.replace(_FINDING, code=Rule.PYR406)

    assert finding.level is Rule.PYR406.severity


def test_rich_finding_serialises_and_validates() -> None:
    """A finding with labelled spans, an enclosing symbol and two fixes validates as a Finding."""
    document = _serialised(finding=_method_finding())
    spans = cast("list[Json]", document["spans"])
    fixes = cast("list[Json]", document["fixes"])

    assert (document["code"], document["level"]) == (Rule.PYR402.name, Rule.PYR402.severity.value)
    assert document["enclosing_symbol"] == {"kind": "method", "name": "Store.save"}
    assert (spans[0]["label"], spans[1]["label"]) == ("defined here", "called here")
    assert (fixes[0]["applicability"], fixes[1]["applicability"]) == ("safe", "unsafe")


def test_rich_finding_spans_cover_their_source_text() -> None:
    """The spans built from real source code cover the text they claim to."""
    function_span, call_span = _method_finding().spans

    function_start, function_end = function_span.byte_start, function_span.byte_end
    call_start, call_end = call_span.byte_start, call_span.byte_end

    assert _METHOD_SOURCE[function_start:function_end].startswith(b"def save(")
    assert _METHOD_SOURCE[call_start:call_end] == _CALL_TEXT


def test_rich_finding_edits_cover_their_source_text() -> None:
    """The edits built from real source code replace the text they claim to."""
    keyword_fix, call_fix = _method_finding().fixes

    assert _applied(fix=keyword_fix) == _METHOD_SOURCE.replace(_PARAMETERS_TEXT, _KEYWORD_PARAMETERS_TEXT)
    assert _applied(fix=call_fix) == _METHOD_SOURCE.replace(_CALL_TEXT, _KEYWORD_CALL_TEXT)


def test_single_span_finding_omits_absent_optional_values() -> None:
    """Absent optional values are omitted, and the list of fixes is present even when empty."""
    document = _serialised(finding=_FINDING)

    assert set(document) == set(_DEFINITIONS["Finding"]["required"])
    assert set(cast("list[Json]", document["spans"])[0]) == set(_DEFINITIONS["Span"]["required"])
    assert document["fixes"] == []


@pytest.mark.parametrize("rule", list(Rule), ids=lambda rule: rule.name)
def test_every_rule_serialises_to_valid_code_and_level(*, rule: Rule) -> None:
    """Every rule's code and severity serialise to values the schema accepts."""
    document = _serialised(finding=dataclasses.replace(_FINDING, code=rule))

    assert (document["code"], document["level"]) == (rule.name, rule.severity.value)


@pytest.mark.parametrize("applicability", [Applicability.SAFE, Applicability.UNSAFE, Applicability.DISPLAY])
def test_every_applicability_serialises_and_validates(*, applicability: Applicability) -> None:
    """Every applicability serialises to a value the schema accepts."""
    finding = dataclasses.replace(_FINDING, fixes=(dataclasses.replace(_FIX, applicability=applicability),))

    document = _serialised(finding=finding)

    assert cast("list[Json]", document["fixes"])[0]["applicability"] == applicability.value


@pytest.mark.parametrize(
    "symbol",
    [
        pytest.param(EnclosingSymbol(kind=SymbolKind.MODULE, name="<module>"), id="module"),
        pytest.param(EnclosingSymbol(kind=SymbolKind.FUNCTION, name="outer.<locals>.inner"), id="nested-function"),
        pytest.param(EnclosingSymbol(kind=SymbolKind.CLASS, name="Outer." + chr(0x3A9)), id="non-ascii-class"),
    ],
)
def test_enclosing_symbol_serialises_and_validates(*, symbol: EnclosingSymbol) -> None:
    """Qualified names Python produces are accepted and serialise to valid findings."""
    document = _serialised(finding=dataclasses.replace(_FINDING, enclosing_symbol=symbol))

    assert document["enclosing_symbol"] == {"kind": symbol.kind.value, "name": symbol.name}


def test_zero_width_span_is_allowed() -> None:
    """A span whose start equals its end is valid."""
    span = dataclasses.replace(_SPAN, byte_end=_SPAN.byte_start, column_end=_SPAN.column_start)

    assert span.byte_start == span.byte_end


def test_later_line_with_smaller_column_is_allowed() -> None:
    """A multi-line span may end at a smaller column than it starts at."""
    span = dataclasses.replace(_SPAN, line_end=LineNumber(2), column_end=ColumnNumber(1))

    assert span.column_end < span.column_start


def test_zero_width_edit_is_allowed() -> None:
    """An edit whose start equals its end inserts, and a fix accepts it."""
    fix = dataclasses.replace(_FIX, edits=_edits((3, 3)))

    assert fix.edits[0].byte_start == fix.edits[0].byte_end


@pytest.mark.parametrize(
    "ranges",
    [
        pytest.param(((0, 3), (3, 5)), id="touching"),
        pytest.param(((3, 3), (3, 5)), id="insertion-before-replacement"),
        pytest.param(((1, 3), (3, 3)), id="insertion-after-replacement"),
        pytest.param(((3, 3), (4, 4)), id="insertions-at-different-offsets"),
    ],
)
def test_touching_edits_are_allowed(*, ranges: tuple[tuple[int, int], ...]) -> None:
    """Edits that touch without overlapping are valid."""
    fix = dataclasses.replace(_FIX, edits=_edits(*ranges))

    assert [(edit.byte_start, edit.byte_end) for edit in fix.edits] == list(ranges)


def test_byte_start_after_byte_end_is_rejected() -> None:
    """A span cannot end before it starts in bytes."""
    with pytest.raises(ValueError, match=r"^byte_start is after byte_end$"):
        dataclasses.replace(_SPAN, byte_start=ByteOffset(10))


def test_line_start_after_line_end_is_rejected() -> None:
    """A span cannot end on an earlier line than it starts on."""
    with pytest.raises(ValueError, match=r"^start position is after its end position$"):
        dataclasses.replace(_SPAN, line_start=LineNumber(2))


def test_column_start_after_column_end_on_one_line_is_rejected() -> None:
    """A single-line span cannot end at an earlier column than it starts at."""
    with pytest.raises(ValueError, match=r"^start position is after its end position$"):
        dataclasses.replace(_SPAN, column_start=ColumnNumber(11))


def test_empty_spans_are_rejected() -> None:
    """A finding needs a location."""
    with pytest.raises(ValueError, match=r"^a finding needs at least one span$"):
        dataclasses.replace(_FINDING, spans=())


def test_zero_primary_spans_are_rejected() -> None:
    """A finding without a primary span has no focal location."""
    with pytest.raises(ValueError, match=r"^a finding needs exactly one primary span$"):
        dataclasses.replace(_FINDING, spans=(dataclasses.replace(_SPAN, is_primary=False),))


def test_two_primary_spans_are_rejected() -> None:
    """A finding with two primary spans lets consumers show different locations."""
    other = dataclasses.replace(_SPAN, byte_start=ByteOffset(0), column_start=ColumnNumber(1))

    with pytest.raises(ValueError, match=r"^a finding needs exactly one primary span$"):
        dataclasses.replace(_FINDING, spans=(_SPAN, other))


def test_repeated_span_is_rejected() -> None:
    """Spans within a finding are unique."""
    secondary = dataclasses.replace(_SPAN, is_primary=False)

    with pytest.raises(ValueError, match=r"^spans repeat$"):
        dataclasses.replace(_FINDING, spans=(_SPAN, secondary, secondary))


def test_repeated_fix_is_rejected() -> None:
    """Fixes within a finding are unique."""
    with pytest.raises(ValueError, match=r"^fixes repeat$"):
        dataclasses.replace(_FINDING, fixes=(_FIX, _FIX))


def test_fix_without_edits_is_rejected() -> None:
    """A fix must change something."""
    with pytest.raises(ValueError, match=r"^a fix needs at least one edit$"):
        dataclasses.replace(_FIX, edits=())


def test_edits_in_different_files_are_rejected() -> None:
    """The edits of one fix are all in the same file."""
    other_file = dataclasses.replace(_edit(byte_start=2, byte_end=3), file_name=FileName("src/other.py"))

    with pytest.raises(ValueError, match=r"^edits of one fix are in different files$"):
        dataclasses.replace(_FIX, edits=(_EDIT, other_file))


def test_overlapping_edits_are_rejected() -> None:
    """Sorted edits whose ranges overlap cannot be applied together."""
    with pytest.raises(ValueError, match=r"^edits overlap$"):
        dataclasses.replace(_FIX, edits=_edits((0, 5), (2, 3)))


def test_unsorted_edits_are_rejected() -> None:
    """Edits are sorted by byte_start."""
    with pytest.raises(ValueError, match=r"^edits are not sorted$"):
        dataclasses.replace(_FIX, edits=_edits((4, 5), (0, 1)))


def test_unsorted_edits_with_equal_start_are_rejected() -> None:
    """Edits with the same start are sorted by byte_end."""
    with pytest.raises(ValueError, match=r"^edits are not sorted$"):
        dataclasses.replace(_FIX, edits=_edits((3, 5), (3, 3)))


def test_two_zero_width_edits_at_same_offset_are_rejected() -> None:
    """Two insertions at one offset have no defined order."""
    with pytest.raises(ValueError, match=r"^edits share a range$"):
        dataclasses.replace(_FIX, edits=_edits((3, 3), (3, 3)))


def test_edit_byte_start_after_byte_end_is_rejected() -> None:
    """An edit cannot end before it starts."""
    with pytest.raises(ValueError, match=r"^byte_start is after byte_end$"):
        dataclasses.replace(_EDIT, byte_start=ByteOffset(5))


@pytest.mark.parametrize(
    ("build", "field"),
    [
        pytest.param(
            lambda: dataclasses.replace(_SPAN, file_name=FileName(_LONE_SURROGATE)), "file_name", id="span-file-name"
        ),
        pytest.param(lambda: dataclasses.replace(_SPAN, label=_LONE_SURROGATE), "label", id="label"),
        pytest.param(
            lambda: dataclasses.replace(_EDIT, file_name=FileName(_LONE_SURROGATE)), "file_name", id="edit-file-name"
        ),
        pytest.param(lambda: dataclasses.replace(_EDIT, content=_LONE_SURROGATE), "content", id="content"),
        pytest.param(lambda: dataclasses.replace(_FIX, message=_LONE_SURROGATE), "message", id="fix-message"),
        pytest.param(lambda: dataclasses.replace(_FINDING, message=_LONE_SURROGATE), "message", id="finding-message"),
        pytest.param(lambda: EnclosingSymbol(kind=SymbolKind.FUNCTION, name=_LONE_SURROGATE), "name", id="symbol-name"),
    ],
)
def test_lone_surrogate_is_rejected(*, build: Callable[[], object], field: str) -> None:
    """Strings are valid Unicode, so a lone surrogate cannot be serialised as UTF-8."""
    with pytest.raises(ValueError, match=rf"^{field} contains a lone surrogate$"):
        build()


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(lambda: dataclasses.replace(_SPAN, file_name=_DECOMPOSED_FILE_NAME), id="span"),
        pytest.param(lambda: dataclasses.replace(_EDIT, file_name=_DECOMPOSED_FILE_NAME), id="edit"),
    ],
)
def test_file_name_not_in_nfc_is_rejected(*, build: Callable[[], object]) -> None:
    """A decomposed file name would make one file look like two."""
    with pytest.raises(ValueError, match=r"^file_name is not in Unicode normalisation form NFC$"):
        build()


def test_file_name_in_nfc_is_accepted() -> None:
    """A composed non-ASCII file name is valid."""
    span = dataclasses.replace(_SPAN, file_name=_COMPOSED_FILE_NAME)

    assert span.file_name == _COMPOSED_FILE_NAME


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("Store.9save", id="segment-starts-with-digit"),
        pytest.param("Store..save", id="empty-segment"),
        pytest.param("Store.sa ve", id="space"),
        pytest.param("<lambda>", id="lambda"),
        pytest.param("<module>", id="module-name"),
        pytest.param("outer.<locals>", id="locals-without-name"),
        pytest.param("outer.<locals>.9inner", id="digit-after-locals"),
        pytest.param("<locals>.inner", id="locals-without-outer"),
    ],
)
def test_symbol_name_with_non_identifier_segment_is_rejected(*, name: str) -> None:
    """Every segment of a qualified name is a Python identifier, except a <locals> segment inside the name."""
    with pytest.raises(ValueError, match=r"^name .* is not a Python __qualname__$"):
        EnclosingSymbol(kind=SymbolKind.METHOD, name=name)


def test_only_findings_module_constructs_spans() -> None:
    """Every span in pyrigor comes from make_span, the only place that calls the Span constructor."""
    package = REPOSITORY_ROOT / "pyrigor"
    python_files = sorted(package.rglob("*.py"))

    constructing = [
        path.relative_to(package).as_posix() for path in python_files if _SPAN_CONSTRUCTOR in _called_names(path=path)
    ]

    assert constructing == ["findings.py"]
