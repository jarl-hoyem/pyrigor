"""Tests for the v2 diagnostics schema: its finding types, invariants and worked position examples."""

import ast
import copy
import json
import re
from pathlib import Path
from typing import Any, NamedTuple, cast

import jsonschema
import pytest
from jsonschema.protocols import Validator

_SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "pyrigor-diagnostics-v2.json"
_BYTE_ORDER_MARK = b"\xef\xbb\xbf"
_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_REQUIRED_EXAMPLE_NAMES = frozenset(
    {
        "line feed",
        "byte-order mark on line 1",
        "CRLF",
        "lone carriage return",
        "line separator inside a string",
        "form feed inside a string",
        "2-byte character before on the same line",
        "3-byte character before on the same line",
        "4-byte character before on the same line",
        "whole line without its break",
        "whole line with its break",
        "whole CRLF line with its break",
        "end of file after a final line break",
        "end of file without a final line break",
    },
)

# JSON documents are untyped by nature. Any matches the jsonschema stubs' own instance type.
Json = dict[str, Any]


class _Position(NamedTuple):
    """A 1-based line and column."""

    line: int
    column: int


def _require_schema_file(*, path: Path) -> None:
    """Fail, rather than skip, when the schema file is missing."""
    if not path.is_file():
        pytest.fail(f"schema file not found: {path}")


def _load_schema() -> Json:
    """Load the schema."""
    _require_schema_file(path=_SCHEMA_PATH)
    return cast("Json", json.loads(_SCHEMA_PATH.read_text(encoding="utf-8")))


def _validator(*, definition: str) -> Validator:
    """Build a validator for one definition of the schema."""
    schema = _load_schema()
    return jsonschema.Draft202012Validator({**schema, "$ref": f"#/$defs/{definition}"})


def _span(*, is_primary: bool = True, file_name: str = "src/app.py") -> Json:
    """Build a valid single-line span."""
    return {
        "file_name": file_name,
        "byte_start": 4,
        "byte_end": 9,
        "line_start": 1,
        "column_start": 5,
        "line_end": 1,
        "column_end": 10,
        "is_primary": is_primary,
    }


def _edit(*, byte_start: int, byte_end: int, content: str) -> Json:
    """Build a valid edit in the primary file."""
    return {"file_name": "src/app.py", "byte_start": byte_start, "byte_end": byte_end, "content": content}


def _finding() -> Json:
    """Build a minimal valid finding."""
    return {
        "code": "PYR402",
        "message": "Function 'apply' has positional parameters; all parameters should be keyword-only",
        "level": "warning",
        "spans": [_span()],
        "fixes": [],
    }


def _with_labelled_spans() -> Json:
    """Build a finding with a labelled primary span and a secondary span in another file."""
    finding = _finding()
    primary = {**_span(), "label": "defined here"}
    secondary = {**_span(is_primary=False, file_name="src/other.py"), "label": "used here"}
    finding["spans"] = [primary, secondary]
    return finding


def _with_enclosing_symbol() -> Json:
    """Build a finding inside a nested function."""
    return {**_finding(), "enclosing_symbol": {"kind": "function", "name": "outer.<locals>.inner"}}


def _with_alternative_fixes() -> Json:
    """Build a finding with two alternative fixes, including touching and zero-width edits."""
    return {
        **_finding(),
        "fixes": [
            {
                "applicability": "unsafe",
                "message": "Make the parameters keyword-only",
                "edits": [_edit(byte_start=10, byte_end=10, content="*, ")],
            },
            {
                "applicability": "display",
                "message": "Rename and make the parameters keyword-only",
                "edits": [
                    _edit(byte_start=4, byte_end=9, content="apply_all"),
                    _edit(byte_start=9, byte_end=10, content="(*, "),
                ],
            },
        ],
    }


def _is_valid(*, definition: str, instance: Json) -> bool:
    """Return whether an instance validates against one definition."""
    return _validator(definition=definition).is_valid(instance)


def test_schema_file_is_valid_json_schema_2020_12() -> None:
    """The schema itself conforms to the JSON Schema 2020-12 meta-schema."""
    jsonschema.Draft202012Validator.check_schema(_load_schema())


def test_missing_schema_file_fails_instead_of_skipping(*, tmp_path: Path) -> None:
    """A missing schema file is a test failure, not a skipped test."""
    with pytest.raises(pytest.fail.Exception, match="schema file not found"):
        _require_schema_file(path=tmp_path / "missing.json")


@pytest.mark.parametrize(
    "finding",
    [
        pytest.param(_finding(), id="single-span"),
        pytest.param(_with_labelled_spans(), id="labelled-spans-across-files"),
        pytest.param(_with_enclosing_symbol(), id="enclosing-symbol"),
        pytest.param(_with_alternative_fixes(), id="alternative-fixes"),
    ],
)
def test_valid_findings_validate(*, finding: Json) -> None:
    """Findings covering each model feature validate."""
    _validator(definition="Finding").validate(finding)


@pytest.mark.parametrize(
    "kind",
    ["function", "method", "class", "module"],
)
def test_every_enclosing_symbol_kind_validates(*, kind: str) -> None:
    """Each enclosing symbol kind is accepted."""
    assert _is_valid(definition="EnclosingSymbol", instance={"kind": kind, "name": "<module>"})


def test_empty_edit_content_is_a_deletion() -> None:
    """An edit with empty content validates because it deletes its range."""
    assert _is_valid(definition="Edit", instance=_edit(byte_start=0, byte_end=3, content=""))


def _without(*, instance: Json, key: str) -> Json:
    """Return a copy of an instance without one key."""
    result = copy.deepcopy(instance)
    del result[key]
    return result


def _first_span(*, finding: Json) -> Json:
    """Return the first span of a finding."""
    return cast("list[Json]", finding["spans"])[0]


def _first_edit(*, finding: Json) -> Json:
    """Return the first edit in a finding's first fix."""
    fix = cast("list[Json]", finding["fixes"])[0]
    return cast("list[Json]", fix["edits"])[0]


def _invalid_findings() -> list[object]:
    """Build one invalid finding per rule the schema enforces."""
    no_primary = _finding()
    _first_span(finding=no_primary)["is_primary"] = False
    two_primaries = _finding()
    two_primaries["spans"] = [_span(), _span()]
    empty_spans: Json = {**_finding(), "spans": []}
    edit_with_primary = _with_alternative_fixes()
    _first_edit(finding=edit_with_primary)["is_primary"] = True
    edit_with_line = _with_alternative_fixes()
    _first_edit(finding=edit_with_line)["line_start"] = 1
    fix_without_edits = _with_alternative_fixes()
    cast("list[Json]", fix_without_edits["fixes"])[0]["edits"] = []
    negative_byte = _finding()
    _first_span(finding=negative_byte)["byte_start"] = -1
    zero_column = _finding()
    _first_span(finding=zero_column)["column_start"] = 0
    null_label = _finding()
    _first_span(finding=null_label)["label"] = None
    empty_label = _finding()
    _first_span(finding=empty_label)["label"] = ""
    unknown_span_field = _finding()
    _first_span(finding=unknown_span_field)["cell"] = 1
    return [
        pytest.param(no_primary, id="zero-primary-spans"),
        pytest.param(two_primaries, id="two-primary-spans"),
        pytest.param(empty_spans, id="empty-spans"),
        *[
            pytest.param(_without(instance=_finding(), key=key), id=f"missing-{key}")
            for key in ("code", "message", "level", "spans", "fixes")
        ],
        pytest.param({**_finding(), "children": []}, id="unknown-finding-field"),
        pytest.param(unknown_span_field, id="unknown-span-field"),
        pytest.param(edit_with_primary, id="edit-with-is-primary"),
        pytest.param(edit_with_line, id="edit-with-line-field"),
        pytest.param(fix_without_edits, id="fix-without-edits"),
        pytest.param({**_finding(), "level": "note"}, id="invalid-level"),
        pytest.param({**_finding(), "code": "E501"}, id="invalid-code"),
        pytest.param({**_finding(), "message": ""}, id="empty-message"),
        pytest.param({**_finding(), "fixes": None}, id="null-fixes"),
        pytest.param({**_finding(), "enclosing_symbol": {"kind": "lambda", "name": "f"}}, id="invalid-symbol-kind"),
        pytest.param({**_finding(), "enclosing_symbol": None}, id="null-enclosing-symbol"),
        pytest.param(negative_byte, id="negative-byte-offset"),
        pytest.param(zero_column, id="zero-column"),
        pytest.param(null_label, id="null-label"),
        pytest.param(empty_label, id="empty-label"),
    ]


@pytest.mark.parametrize("finding", _invalid_findings())
def test_invalid_findings_are_rejected(*, finding: Json) -> None:
    """Each violation of a rule the schema enforces is rejected."""
    assert not _is_valid(definition="Finding", instance=finding)


@pytest.mark.parametrize(
    "fix",
    [
        pytest.param(
            {"applicability": "safe", "message": "m", "edits": [_edit(byte_start=0, byte_end=0, content="x")]},
            id="safe",
        ),
        pytest.param(
            {"applicability": "unsafe", "message": "m", "edits": [_edit(byte_start=0, byte_end=0, content="x")]},
            id="unsafe",
        ),
        pytest.param(
            {"applicability": "display", "message": "m", "edits": [_edit(byte_start=0, byte_end=0, content="x")]},
            id="display",
        ),
    ],
)
def test_every_applicability_validates(*, fix: Json) -> None:
    """Each applicability value is accepted."""
    assert _is_valid(definition="Fix", instance=fix)


def test_invalid_applicability_is_rejected() -> None:
    """An applicability value outside the three allowed values is rejected."""
    fix: Json = {"applicability": "suggestion", "message": "m", "edits": [_edit(byte_start=0, byte_end=0, content="x")]}
    assert not _is_valid(definition="Fix", instance=fix)


def _position_examples() -> list[Json]:
    """Return the worked position examples for spans."""
    return cast("list[Json]", _load_schema()["x-span-position-examples"])


def _reference_position(*, raw: bytes, offset: int) -> _Position:
    """Compute a line and column from raw bytes, independently of pyrigor's code."""
    body_start = len(_BYTE_ORDER_MARK) if raw.startswith(_BYTE_ORDER_MARK) else 0
    before = raw[body_start:offset].decode()
    breaks = list(_LINE_BREAK.finditer(before))
    line_start = breaks[-1].end() if breaks else 0
    line_text = before[line_start:]
    return _Position(line=len(breaks) + 1, column=len(line_text) + 1)


def test_position_examples_cover_every_required_case() -> None:
    """The worked examples include every edge case the position conventions must illustrate."""
    names = {cast("str", example["name"]) for example in _position_examples()}

    assert names == _REQUIRED_EXAMPLE_NAMES


@pytest.mark.parametrize("example", _position_examples(), ids=lambda example: cast("str", example["name"]))
def test_position_example_bytes_match_its_text(*, example: Json) -> None:
    """Each example's byte range slices its exact text out of the encoded source."""
    raw = cast("str", example["source"]).encode()
    byte_start = cast("int", example["byte_start"])
    byte_end = cast("int", example["byte_end"])

    assert raw[byte_start:byte_end].decode() == example["text"]


@pytest.mark.parametrize("example", _position_examples(), ids=lambda example: cast("str", example["name"]))
def test_position_example_lines_and_columns_follow_the_conventions(*, example: Json) -> None:
    """Each example's lines and columns follow the stated conventions."""
    raw = cast("str", example["source"]).encode()

    start = _reference_position(raw=raw, offset=cast("int", example["byte_start"]))
    end = _reference_position(raw=raw, offset=cast("int", example["byte_end"]))

    assert start == _Position(line=cast("int", example["line_start"]), column=cast("int", example["column_start"]))
    assert end == _Position(line=cast("int", example["line_end"]), column=cast("int", example["column_end"]))


@pytest.mark.parametrize(
    "name",
    ["lone carriage return", "line separator inside a string", "form feed inside a string", "CRLF"],
)
def test_position_example_lines_agree_with_python_parser(*, name: str) -> None:
    """The line-break convention matches where Python's parser puts the flagged function."""
    example = _position_example(name=name)

    function = _first_function(source=cast("str", example["source"]))

    assert function.lineno == example["line_start"]


def _position_example(*, name: str) -> Json:
    """Return the worked position example with the given name."""
    return {cast("str", example["name"]): example for example in _position_examples()}[name]


def _first_function(*, source: str) -> ast.FunctionDef:
    """Parse source from its encoded bytes and return its first function definition."""
    functions = [node for node in ast.walk(ast.parse(source.encode())) if isinstance(node, ast.FunctionDef)]
    return functions[0]
