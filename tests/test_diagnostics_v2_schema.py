"""Tests for the v2 diagnostics schema: its types, hostile inputs, known limits and worked position examples."""

import ast
import copy
import json
import math
import re
from pathlib import Path
from typing import Any, NamedTuple, cast

import jsonschema
import pytest
from jsonschema.protocols import Validator

_SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "pyrigor-diagnostics-v2.json"
_BYTE_ORDER_MARK = b"\xef\xbb\xbf"
_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_LARGEST_SAFE_INTEGER = 9_007_199_254_740_991  # 2 to the 53rd power, minus 1
_NAMED_SCHEMA_MAPS = frozenset({"properties", "$defs"})
_EXTENSION_POLICY_KEY = "x-extension-policy"
_EXTENSION_POLICY_RULES = (
    "ignore fields they do not know",
    "optional field is a compatible change",
    "changes the version",
)
_QUADRATIC_KEYWORD = "uniqueItems"
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

# Every keyword JSON Schema 2020-12 defines. Validators silently ignore a misspelt keyword, so any other key must be
# an extension key starting with x-.
_KNOWN_KEYWORDS = frozenset(
    {
        "$schema",
        "$id",
        "$ref",
        "$defs",
        "$comment",
        "$anchor",
        "$dynamicRef",
        "$dynamicAnchor",
        "$vocabulary",
        "title",
        "description",
        "default",
        "deprecated",
        "readOnly",
        "writeOnly",
        "examples",
        "type",
        "enum",
        "const",
        "multipleOf",
        "maximum",
        "exclusiveMaximum",
        "minimum",
        "exclusiveMinimum",
        "maxLength",
        "minLength",
        "pattern",
        "maxItems",
        "minItems",
        "uniqueItems",
        "maxContains",
        "minContains",
        "maxProperties",
        "minProperties",
        "required",
        "dependentRequired",
        "allOf",
        "anyOf",
        "oneOf",
        "not",
        "if",
        "then",
        "else",
        "dependentSchemas",
        "prefixItems",
        "items",
        "contains",
        "properties",
        "patternProperties",
        "additionalProperties",
        "propertyNames",
        "unevaluatedItems",
        "unevaluatedProperties",
        "format",
        "contentEncoding",
        "contentMediaType",
        "contentSchema",
    },
)

# JSON documents are untyped by nature. Any matches the jsonschema stubs' own instance type.
Json = dict[str, Any]
JsonValue = Json | list[Any] | None


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


def _root_validator() -> Validator:
    """Build a validator for the schema root, which is how a whole document is validated."""
    return jsonschema.Draft202012Validator(_load_schema())


def _validator(*, definition: str) -> Validator:
    """Build a validator for one definition, without the root's rejection of every document."""
    schema = _load_schema()
    schema.pop("not", None)
    return jsonschema.Draft202012Validator({**schema, "$ref": f"#/$defs/{definition}"})


def _span(**overrides: object) -> Json:
    """Build a valid single-line primary span, with some fields replaced."""
    span: Json = {
        "file_name": "src/app.py",
        "byte_start": 4,
        "byte_end": 9,
        "line_start": 1,
        "column_start": 5,
        "line_end": 1,
        "column_end": 10,
        "is_primary": True,
    }
    return {**span, **overrides}


def _edit(*, byte_start: int = 0, byte_end: int = 0, content: str = "x", file_name: str = "src/app.py") -> Json:
    """Build a valid edit."""
    return {"file_name": file_name, "byte_start": byte_start, "byte_end": byte_end, "content": content}


def _finding(**overrides: object) -> Json:
    """Build a minimal valid finding, with some fields replaced."""
    finding: Json = {
        "code": "PYR402",
        "message": "Function 'apply' has positional parameters; all parameters should be keyword-only",
        "level": "warning",
        "spans": [_span()],
        "fixes": [],
    }
    return {**copy.deepcopy(finding), **overrides}


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


def test_schema_states_its_extension_policy() -> None:
    """The top-level description points to the extension policy, and the policy states each rule."""
    schema = _load_schema()
    policy = " ".join(cast("list[str]", schema[_EXTENSION_POLICY_KEY]))

    missing = [rule for rule in _EXTENSION_POLICY_RULES if rule not in policy]

    assert _EXTENSION_POLICY_KEY in cast("str", schema["description"])
    assert not missing


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
    ("kind", "name"),
    [("function", "apply"), ("method", "Report.render"), ("class", "Report"), ("module", "<module>")],
)
def test_every_enclosing_symbol_kind_validates(*, kind: str, name: str) -> None:
    """Each enclosing symbol kind is accepted with a name of that kind."""
    assert _is_valid(definition="EnclosingSymbol", instance={"kind": kind, "name": name})


def test_empty_edit_content_is_a_deletion() -> None:
    """An edit with empty content validates because it deletes its range."""
    assert _is_valid(definition="Edit", instance=_edit(byte_end=3, content=""))


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
    two_primaries["spans"] = [_span(), _span(file_name="src/other.py")]
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
        pytest.param({"applicability": "safe", "message": "m", "edits": [_edit()]}, id="safe"),
        pytest.param({"applicability": "unsafe", "message": "m", "edits": [_edit()]}, id="unsafe"),
        pytest.param({"applicability": "display", "message": "m", "edits": [_edit()]}, id="display"),
    ],
)
def test_every_applicability_validates(*, fix: Json) -> None:
    """Each applicability value is accepted."""
    assert _is_valid(definition="Fix", instance=fix)


def test_invalid_applicability_is_rejected() -> None:
    """An applicability value outside the three allowed values is rejected."""
    fix: Json = {"applicability": "suggestion", "message": "m", "edits": [_edit()]}
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


def _with_fix(*, edits: list[Json]) -> Json:
    """Build a valid finding with one fix made of the given edits."""
    return _finding(fixes=[{"applicability": "safe", "message": "m", "edits": edits}])


def _symbol(*, kind: str, name: str) -> Json:
    """Build a finding with the given enclosing symbol."""
    return _finding(enclosing_symbol={"kind": kind, "name": name})


_HOSTILE_FILE_NAMES = {
    "backslash": "src\\app.py",
    "absolute": "/src/app.py",
    "drive-letter": "C:/app.py",
    "parent-segment-at-start": "../app.py",
    "parent-segment-inside": "src/../app.py",
    "parent-segment-at-end": "src/..",
    "trailing-newline": "src/app.py\n",
    "tab": "src/\tapp.py",
    "c1-control-character": "src/\x85app.py",
    "empty-segment": "src//app.py",
    "trailing-slash": "src/",
    "empty": "",
    "bidi-override": "src/app\u202e.py",
    "bidi-isolate": "src/\u2066app.py",
    "zero-width-space": "src/ap\u200bp.py",
    "byte-order-mark-character": "\ufeffsrc/app.py",
    "dot-segment-inside": "src/./app.py",
    "dot-segment-at-start": "./app.py",
    "dot-segment-alone": ".",
    "trailing-space-in-segment": "src /app.py",
    "leading-space-in-segment": "src/ app.py",
    "trailing-space-in-name": "src/app.py ",
    "control-character-inside-segment": "src/a\x07pp.py",
    "c1-control-character-inside-segment": "src/a\x9bpp.py",
}


def _hostile_file_name_findings() -> list[object]:
    """Build one finding per hostile file name, used once in a span and once in an edit."""
    return [
        pytest.param(finding, id=f"{place}-{name}")
        for name, file_name in _HOSTILE_FILE_NAMES.items()
        for place, finding in (
            ("span", _finding(spans=[_span(file_name=file_name)])),
            ("edit", _with_fix(edits=[_edit(file_name=file_name)])),
        )
    ]


@pytest.mark.parametrize("finding", _hostile_file_name_findings())
def test_hostile_file_name_is_rejected_in_spans_and_edits(*, finding: Json) -> None:
    """Each hostile file name is rejected wherever a file name appears."""
    assert not _is_valid(definition="Finding", instance=finding)


@pytest.mark.parametrize(
    "finding",
    [
        pytest.param(_finding(code="PYR402\n"), id="code-with-trailing-newline"),
        pytest.param(_finding(code="PYR\u0664\u0660\u0662"), id="code-with-non-ascii-digits"),
        pytest.param(_finding(code="pyr402"), id="code-in-lowercase"),
        pytest.param(_finding(message="   "), id="whitespace-only-message"),
        pytest.param(_finding(message="\n"), id="newline-only-message"),
        pytest.param(_finding(spans=[_span(label=" ")]), id="whitespace-only-label"),
        pytest.param(_finding(spans=[_span(byte_end=_LARGEST_SAFE_INTEGER + 1)]), id="byte-offset-beyond-safe-integer"),
        pytest.param(_finding(spans=[_span(line_end=_LARGEST_SAFE_INTEGER + 1)]), id="line-beyond-safe-integer"),
        pytest.param(_with_fix(edits=[_edit(byte_end=_LARGEST_SAFE_INTEGER + 1)]), id="edit-beyond-safe-integer"),
        pytest.param(_finding(spans=[_span(is_primary=1)]), id="integer-as-is-primary"),
        pytest.param(_finding(spans=[_span(byte_start=True)]), id="boolean-as-byte-offset"),
        pytest.param(_symbol(kind="module", name="apply"), id="module-kind-with-function-name"),
        pytest.param(_symbol(kind="function", name="<module>"), id="function-kind-named-module"),
        pytest.param(_symbol(kind="function", name="not a name"), id="symbol-name-with-spaces"),
        pytest.param(_symbol(kind="function", name="apply\n"), id="symbol-name-with-trailing-newline"),
        pytest.param(_symbol(kind="method", name="Class..method"), id="symbol-name-with-empty-segment"),
        pytest.param(_symbol(kind="function", name=".apply"), id="symbol-name-starting-with-dot"),
        pytest.param(_symbol(kind="function", name="outer.<lambda>"), id="lambda-as-symbol"),
        pytest.param(_symbol(kind="function", name="ap\u2066ply"), id="bidi-isolate-in-symbol-name"),
        pytest.param(_symbol(kind="function", name="ap\u200bply"), id="zero-width-space-in-symbol-name"),
        pytest.param(_symbol(kind="method", name="render"), id="method-without-class"),
        pytest.param(_symbol(kind="method", name="outer.<locals>.inner"), id="method-directly-in-function"),
        pytest.param(_symbol(kind="function", name="Report.render"), id="function-directly-in-class"),
        pytest.param(_symbol(kind="class", name="<module>"), id="class-kind-named-module"),
        pytest.param(
            _finding(fixes=[{"applicability": "safe", "message": " ", "edits": [_edit()]}]),
            id="whitespace-only-fix-message",
        ),
        pytest.param(
            _finding(fixes=[{"applicability": "safe", "message": "apply\u202e", "edits": [_edit()]}]),
            id="bidi-override-in-fix-message",
        ),
        pytest.param(_finding(message="ok\u202e"), id="bidi-override-in-message"),
        pytest.param(_finding(message="\u200b"), id="zero-width-only-message"),
        pytest.param(_finding(message="\u200b\u2060\ufeff "), id="invisible-only-message"),
        pytest.param(_finding(spans=[_span(label="here\u2067")]), id="bidi-isolate-in-label"),
        pytest.param(_finding(spans=[_span(label="\u200d")]), id="zero-width-only-label"),
    ],
)
def test_hostile_finding_is_rejected(*, finding: Json) -> None:
    """A hostile finding the schema can recognise is rejected."""
    assert not _is_valid(definition="Finding", instance=finding)


@pytest.mark.parametrize(
    "finding",
    [
        pytest.param(_symbol(kind="module", name="<module>"), id="module"),
        pytest.param(_symbol(kind="function", name="apply"), id="function"),
        pytest.param(_symbol(kind="method", name="Report.render"), id="method"),
        pytest.param(_symbol(kind="class", name="Report"), id="class"),
        pytest.param(_symbol(kind="function", name="outer.<locals>.inner"), id="nested-function"),
        pytest.param(_symbol(kind="method", name="outer.<locals>.Report.render"), id="method-of-nested-class"),
        pytest.param(_symbol(kind="class", name="Outer.Inner"), id="nested-class"),
        pytest.param(_symbol(kind="class", name="build.<locals>.Report"), id="class-in-function"),
        pytest.param(_finding(spans=[_span(file_name=".github/workflows/ci.py")]), id="dot-directory"),
        pytest.param(_finding(spans=[_span(file_name="src/app.test.py")]), id="dots-in-a-name"),
        pytest.param(_finding(message="Call 'apply' uses \u00e9 and \u00fc"), id="non-ascii-message"),
        pytest.param(_symbol(kind="function", name="\u00e9tape"), id="non-ascii-identifier"),
        pytest.param(_finding(spans=[_span(file_name="app.py")]), id="file-in-working-directory"),
        pytest.param(_finding(spans=[_span(file_name="src/..app.py")]), id="dots-inside-a-segment"),
        pytest.param(_finding(spans=[_span(file_name="src/.hidden/app.py")]), id="hidden-directory"),
        pytest.param(_finding(spans=[_span(byte_end=_LARGEST_SAFE_INTEGER)]), id="largest-safe-integer"),
        pytest.param(_finding(message="Function 'apply' has positional parameters"), id="message-with-spaces"),
    ],
)
def test_boundary_finding_is_accepted(*, finding: Json) -> None:
    """A finding at the edge of a rule is still accepted."""
    assert _is_valid(definition="Finding", instance=finding)


@pytest.mark.parametrize(
    "finding",
    [
        pytest.param(_finding(spans=[_span(byte_start=9, byte_end=4)]), id="byte-end-before-start"),
        pytest.param(_finding(spans=[_span(line_start=5, line_end=2)]), id="line-end-before-start"),
        pytest.param(_with_fix(edits=[_edit(file_name="a.py"), _edit(file_name="b.py")]), id="edits-in-two-files"),
        pytest.param(
            _with_fix(edits=[_edit(byte_end=5), _edit(byte_start=2, byte_end=6)]),
            id="overlapping-edits",
        ),
        pytest.param(
            _with_fix(edits=[_edit(byte_start=5, byte_end=6), _edit(byte_end=1)]),
            id="unsorted-edits",
        ),
        pytest.param(_finding(code="PYR000"), id="code-of-no-rule"),
        pytest.param(_finding(spans=[_span(byte_start=4.0)]), id="integral-float-offset"),
        pytest.param(_finding(spans=[_span(), _span(is_primary=False), _span(is_primary=False)]), id="duplicate-spans"),
        pytest.param(_with_fix(edits=[_edit(), _edit()]), id="duplicate-edits"),
        pytest.param(_finding(spans=[_span(file_name="e\u0301tape.py")]), id="decomposed-file-name"),
        pytest.param(_finding(message="bad\ud800"), id="lone-surrogate-in-message"),
        pytest.param(_finding(spans=[_span(file_name="src/\udc00.py")]), id="lone-surrogate-in-file-name"),
        pytest.param(_with_fix(edits=[{**_edit(), "content": "x = '\u202e'"}]), id="bidi-control-in-edit-content"),
    ],
)
def test_schema_cannot_reject_what_only_the_producer_can_enforce(*, finding: Json) -> None:
    """These are accepted by design and listed in x-invariants, or are integers under JSON Schema's own definition.

    If the schema ever rejects one, move the case to the hostile tests and remove it from x-invariants.
    """
    assert _is_valid(definition="Finding", instance=finding)


@pytest.mark.parametrize(
    "document",
    [
        pytest.param({}, id="empty-object"),
        pytest.param({"anything": 1}, id="arbitrary-object"),
        pytest.param([], id="array"),
        pytest.param(None, id="null"),
    ],
)
def test_no_document_validates_until_the_wrapper_is_defined(*, document: JsonValue) -> None:
    """The root rejects every document, so nothing can pass validation before the wrapper exists."""
    assert not _root_validator().is_valid(document)


@pytest.mark.parametrize(
    "finding",
    [
        pytest.param(_finding(spans=[_span(is_primary=None)]), id="null-is-primary"),
        pytest.param(_finding(spans=[_span(is_primary="true")]), id="string-is-primary"),
        pytest.param(_finding(spans=[_span(byte_start="4")]), id="string-offset"),
        pytest.param(_finding(spans=[_span(byte_start=4.5)]), id="fractional-offset"),
        pytest.param(_finding(spans=[_span(byte_start=math.nan)]), id="nan-offset"),
        pytest.param(_finding(spans=[_span(byte_start=1e300)]), id="huge-float-offset"),
        pytest.param(_finding(level="WARNING"), id="uppercase-level"),
        pytest.param(_finding(level="warning "), id="level-with-trailing-space"),
        pytest.param(
            _finding(fixes=[{"applicability": "SAFE", "message": "m", "edits": [_edit()]}]),
            id="uppercase-applicability",
        ),
        pytest.param(_symbol(kind="Function", name="apply"), id="uppercase-kind"),
        pytest.param(_finding(code=" PYR402"), id="code-with-leading-space"),
        pytest.param(_finding(code="PYR\uff14\uff10\uff12"), id="code-with-fullwidth-digits"),
        pytest.param(
            _finding(fixes=[{"applicability": "safe", "message": "m", "edits": [_edit()], "extra": 1}]),
            id="unknown-fix-field",
        ),
        pytest.param(
            _finding(enclosing_symbol={"kind": "function", "name": "apply", "extra": 1}),
            id="unknown-symbol-field",
        ),
        pytest.param(_finding(spans=_span()), id="spans-as-object"),
        pytest.param(_with_fix(edits=[{**_edit(), "content": None}]), id="null-edit-content"),
        pytest.param(_finding(enclosing_symbol={"kind": "function"}), id="symbol-without-name"),
        pytest.param(_finding(spans=[_span(label=5)]), id="numeric-label"),
    ],
)
def test_malformed_finding_is_rejected(*, finding: Json) -> None:
    """A finding with a wrong type, value or shape is rejected."""
    assert not _is_valid(definition="Finding", instance=finding)


def test_schema_uses_no_quadratic_keyword() -> None:
    """The schema never uses uniqueItems, which would let a hostile finding stall validation.

    uniqueItems compares every item with every other, so thousands of spans took seconds to validate. Uniqueness is a
    producer invariant instead.
    """
    assert _QUADRATIC_KEYWORD not in _schema_keys(node=_load_schema())


def _schema_keys(*, node: object) -> set[str]:
    """Collect every key used in a schema position, not inside property names or data under keys starting with x-."""
    if isinstance(node, list):
        # pyright strict needs the cast after isinstance narrowing
        # noinspection PyUnnecessaryCast
        return _keys_in_list(items=cast("list[object]", node))
    if not isinstance(node, dict):
        return set()
    keys: set[str] = set()
    # pyright strict needs the cast after isinstance narrowing
    # noinspection PyUnnecessaryCast
    for key, value in cast("Json", node).items():
        keys |= {key} | _keys_below(key=key, value=value)
    return keys


def _keys_in_list(*, items: list[object]) -> set[str]:
    """Collect the schema keys of every item in a list."""
    keys: set[str] = set()
    for item in items:
        keys |= _schema_keys(node=item)
    return keys


def _keys_below(*, key: str, value: object) -> set[str]:
    """Collect the schema keys below one keyword's value."""
    if key.startswith("x-"):
        return set()
    if key in _NAMED_SCHEMA_MAPS:
        return _keys_in_list(items=list(cast("Json", value).values()))
    return _schema_keys(node=value)


def test_schema_uses_no_misspelt_keyword() -> None:
    """Every key is a JSON Schema 2020-12 keyword or an extension key starting with x-, so no rule is ignored."""
    keys = _schema_keys(node=_load_schema())

    unknown = {key for key in keys if key not in _KNOWN_KEYWORDS and not key.startswith("x-")}

    assert not unknown
