"""Validate the v2 document wrapper, its examples and its producer-only invariants."""

import copy
from typing import cast

import jsonschema
import pytest
from jsonschema.protocols import Validator

from pyrigor.rules import Applicability, FixAvailability
from tests.diagnostics_v2_support import FILE_NAME, Json, load_v2_schema

# The file, group, record and unit separators and the byte-order mark. The whitespace class of the schema leaves out
# U+001C to U+001F and U+FEFF on purpose, because the control and hidden-character rules reject them elsewhere.
_SEPARATORS_AND_BOM = (0x1C, 0x1D, 0x1E, 0x1F, 0xFEFF)


def _rule(**overrides: object) -> Json:
    """Build metadata for a selected rule, with optional replacements."""
    return {
        "symbolic_name": "keyword-only-arguments",
        "fix_availability": "always",
        "applicability": "unsafe",
        "url": "https://github.com/jarl-hoyem/pyrigor/blob/v0.13.1/guidelines/PYR402-keyword-only-arguments.md",
        **overrides,
    }


def _finding(*, file_name: str = FILE_NAME, code: str = "PYR402") -> Json:
    """Build a finding with one primary source range."""
    return {
        "code": code,
        "message": "Function has positional parameters",
        "level": "warning",
        "spans": [
            {
                "file_name": file_name,
                "byte_start": 0,
                "byte_end": 3,
                "line_start": 1,
                "column_start": 1,
                "line_end": 1,
                "column_end": 4,
                "is_primary": True,
            }
        ],
        "fixes": [],
    }


def _error(**overrides: object) -> Json:
    """Build a positionless parse error, with optional replacements."""
    return {"file_name": FILE_NAME, "kind": "parse_error", "message": "Invalid syntax", **overrides}


def _document(**overrides: object) -> Json:
    """Build a clean run, retaining selected rules that produced no findings."""
    return {
        "schema_version": 2,
        "tool": {"name": "pyrigor", "version": "0.13.1"},
        "findings": [],
        "suppressed": [],
        "rules": {"PYR402": _rule()},
        "errors": [],
        "summary": {"files_checked": 1},
        **overrides,
    }


def _validator() -> Validator:
    """Build a typed validator for the published document root."""
    return jsonschema.Draft202012Validator(load_v2_schema())


def _valid(*, document: Json) -> bool:
    """Validate an entire document through the published schema root."""
    return _validator().is_valid(document)


@pytest.mark.parametrize(
    "document",
    [
        pytest.param(_document(), id="clean-selected-rule"),
        pytest.param(_document(rules={}, summary={"files_checked": 0}), id="empty-run"),
        pytest.param(
            _document(
                findings=[_finding(file_name="a.py"), _finding(file_name="b.py")],
                summary={"files_checked": 2},
            ),
            id="several-files",
        ),
        pytest.param(_document(suppressed=[_finding()]), id="suppressed"),
        pytest.param(_document(errors=[_error(kind="read_error")]), id="unreadable"),
        pytest.param(_document(errors=[_error(line=2, column=3)]), id="parse-position"),
        pytest.param(_document(errors=[_error()]), id="parse-without-position"),
        pytest.param(
            _document(errors=[_error(kind="malformed_suppression", line=2, column=3)]),
            id="malformed-suppression-position",
        ),
        pytest.param(
            _document(errors=[_error(kind="malformed_suppression")]), id="malformed-suppression-without-position"
        ),
        pytest.param(
            _document(findings=[_finding()], suppressed=[_finding(file_name="b.py")], errors=[_error()]),
            id="combined-results",
        ),
    ],
)
def test_document_examples_validate(*, document: Json) -> None:
    """Clean, populated, suppressed and incomplete runs all have a valid document representation."""
    _validator().validate(document)


@pytest.mark.parametrize("field", ["schema_version", "tool", "findings", "suppressed", "rules", "errors", "summary"])
def test_document_requires_each_wrapper_field(*, field: str) -> None:
    """Every required wrapper field is independently enforced, including empty lists."""
    document = _document()
    del document[field]
    assert not _valid(document=document)


@pytest.mark.parametrize("version", [1, "2", None, True, 3])
def test_document_rejects_other_schema_versions(*, version: object) -> None:
    """Only integer schema version two is accepted."""
    assert not _valid(document=_document(schema_version=version))


@pytest.mark.parametrize("part", ["root", "tool", "rules", "error", "summary"])
def test_document_rejects_unknown_wrapper_fields(*, part: str) -> None:
    """The root and every fixed-shape wrapper object reject unrecognised fields."""
    document = _document(errors=[_error()])
    objects = {
        "root": document,
        "tool": document["tool"],
        "rules": document["rules"]["PYR402"],
        "error": document["errors"][0],
        "summary": document["summary"],
    }
    objects[part]["unexpected"] = 1
    assert not _valid(document=document)


@pytest.mark.parametrize(
    ("part", "field"),
    [
        ("tool", "name"),
        ("tool", "version"),
        ("rule", "symbolic_name"),
        ("rule", "fix_availability"),
        ("rule", "url"),
        ("error", "file_name"),
        ("error", "kind"),
        ("error", "message"),
        ("summary", "files_checked"),
    ],
)
def test_document_requires_each_nested_field(*, part: str, field: str) -> None:
    """Every nested required field is checked separately."""
    document = _document(errors=[_error()])
    objects = {
        "tool": document["tool"],
        "rule": document["rules"]["PYR402"],
        "error": document["errors"][0],
        "summary": document["summary"],
    }
    del objects[part][field]
    assert not _valid(document=document)


@pytest.mark.parametrize("code", ["402", "pyr402", "PYR40", "PYR4020", "PYR402\n", "invalid"])
def test_document_rejects_non_rule_keys(*, code: str) -> None:
    """Metadata keys use exactly the same rule-code syntax as findings."""
    assert not _valid(document=_document(rules={code: _rule()}))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("symbolic_name", ""),
        ("symbolic_name", "UpperCase"),
        ("symbolic_name", "name\n"),
        ("symbolic_name", "name\n\n"),
        ("symbolic_name", "name\n\n\n"),
        ("symbolic_name", "-name"),
        ("symbolic_name", "name-"),
        ("symbolic_name", "na--me"),
        ("symbolic_name", "1name"),
        ("symbolic_name", "na_me"),
        ("symbolic_name", "na me"),
        *[("symbolic_name", f"na{chr(code_point)}me") for code_point in _SEPARATORS_AND_BOM],
        *[("url", f"{_rule()['url']}{chr(code_point)}") for code_point in _SEPARATORS_AND_BOM],
        ("symbolic_name", 402),
        ("symbolic_name", None),
        ("fix_availability", "safe_fix"),
        ("applicability", "automatic"),
        ("applicability", None),
        ("url", "https://github.com/jarl-hoyem/pyrigor/blob/main/guidelines/PYR402-keyword-only-arguments.md"),
        ("url", "https://example.com/PYR402.md"),
        ("url", 402),
        ("url", None),
        ("url", "https://github.com/jarl-hoyem/pyrigor/blob/v0.13.1/guidelines/PYR402-keyword-only-arguments.md\n"),
    ],
)
def test_document_rejects_invalid_rule_metadata(*, field: str, value: object) -> None:
    """Rule metadata rejects obsolete vocabulary, malformed names and unpinned URLs."""
    assert not _valid(document=_document(rules={"PYR402": _rule(**{field: value})}))


@pytest.mark.parametrize("availability", ["always", "sometimes"])
@pytest.mark.parametrize("applicability", [item.value for item in Applicability])
def test_fixable_rule_metadata_accepts_each_applicability(*, availability: str, applicability: str) -> None:
    """Both fixable availability values support every established applicability value."""
    assert _valid(
        document=_document(rules={"PYR402": _rule(fix_availability=availability, applicability=applicability)})
    )


@pytest.mark.parametrize("availability", ["always", "sometimes", "none"])
def test_rule_applicability_presence_matches_availability(*, availability: str) -> None:
    """Applicability is required for a fixable rule and omitted for a rule with no fix."""
    rule = _rule(fix_availability=availability)
    assert _valid(document=_document(rules={"PYR402": rule})) == (availability != FixAvailability.NONE.value)
    del rule["applicability"]
    assert _valid(document=_document(rules={"PYR402": rule})) == (availability == FixAvailability.NONE.value)


@pytest.mark.parametrize(
    ("field", "value"),
    [("kind", "crash"), ("kind", ""), ("file_name", "/absolute.py"), ("message", ""), ("message", "bad\ntext")],
)
def test_document_rejects_invalid_operational_errors(*, field: str, value: object) -> None:
    """Operational errors enforce their kinds, relative paths and visible messages."""
    assert not _valid(document=_document(errors=[_error(**{field: value})]))


@pytest.mark.parametrize(
    ("kind", "locatable"), [("parse_error", True), ("malformed_suppression", True), ("read_error", False)]
)
@pytest.mark.parametrize("field", ["line", "column"])
def test_error_positions_are_optional_only_for_locatable_errors(*, kind: str, locatable: bool, field: str) -> None:
    """Parse and suppression errors can carry either coordinate; read errors have no source position."""
    assert _valid(document=_document(errors=[_error(kind=kind, **{field: 1})])) == locatable


@pytest.mark.parametrize("field", ["line", "column"])
@pytest.mark.parametrize("value", [0, -1, 1.5, True, None, 9_007_199_254_740_992])
def test_error_positions_reject_invalid_values(*, field: str, value: object) -> None:
    """Error coordinates use the same positive safe-integer boundary as spans."""
    assert not _valid(document=_document(errors=[_error(**{field: value})]))


@pytest.mark.parametrize("value", [-1, 1.5, True, None, "1", 9_007_199_254_740_992])
def test_summary_rejects_invalid_file_counts(*, value: object) -> None:
    """File counts are non-negative safe integers."""
    assert not _valid(document=_document(summary={"files_checked": value}))


@pytest.mark.parametrize("part", ["findings", "suppressed"])
def test_document_lists_validate_their_findings(*, part: str) -> None:
    """Both lists reference Finding, rather than accepting unvalidated objects."""
    finding = _finding()
    del finding["spans"]
    assert not _valid(document=_document(**{part: [finding]}))


@pytest.mark.parametrize("field", ["tool", "findings", "suppressed", "rules", "errors", "summary"])
def test_wrapper_parts_reject_null(*, field: str) -> None:
    """An absent value is never represented by null, including document collections."""
    assert not _valid(document=_document(**{field: None}))


@pytest.mark.parametrize(
    ("field", "value"),
    [("name", "other"), ("version", ""), ("version", "1 2"), ("version", "1\n"), ("version", "1\x00")],
)
def test_document_rejects_invalid_tool_identity(*, field: str, value: object) -> None:
    """The producer name is fixed, and its version is visible, non-empty text without whitespace."""
    tool = {"name": "pyrigor", "version": "0.13.1", field: value}
    assert not _valid(document=_document(tool=tool))


@pytest.mark.parametrize("value", [0, 9_007_199_254_740_991])
def test_summary_accepts_file_count_boundaries(*, value: int) -> None:
    """A zero-file run and the largest safe integer are both structurally representable."""
    assert _valid(document=_document(summary={"files_checked": value}))


@pytest.mark.parametrize("field", ["line", "column"])
def test_error_positions_accept_the_upper_boundary(*, field: str) -> None:
    """Both error coordinates accept the inclusive upper bound shared with spans."""
    assert _valid(document=_document(errors=[_error(**{field: 9_007_199_254_740_991})]))


@pytest.mark.parametrize("value", ["invalid", None, []])
def test_rule_entries_require_objects(*, value: object) -> None:
    """Every rule key resolves structured metadata."""
    assert not _valid(document=_document(rules={"PYR402": value}))


@pytest.mark.parametrize("field", ["findings", "suppressed", "errors"])
def test_document_collections_require_arrays(*, field: str) -> None:
    """Objects cannot replace the document's result lists."""
    empty_object: Json = {}
    assert not _valid(document=_document(**{field: empty_object}))


def test_wrapper_fix_vocabulary_matches_the_canonical_enums() -> None:
    """The wrapper uses the rule registry's availability and applicability vocabulary."""
    definitions = load_v2_schema()["$defs"]
    assert set(definitions["RuleMetadata"]["properties"]["fix_availability"]["enum"]) == {
        item.value for item in FixAvailability
    }
    assert set(definitions["Fix"]["properties"]["applicability"]["enum"]) == {item.value for item in Applicability}


@pytest.mark.parametrize(
    "case", ["missing-rule", "unselected-rule", "finding-order", "suppressed-order", "error-order", "rule-order"]
)
def test_schema_leaves_cross_references_and_order_to_the_producer(*, case: str) -> None:
    """JSON Schema cannot relate selected rules or impose the ordering contract; #269 must enforce it."""
    document = _document()
    examples: dict[str, Json] = {
        "missing-rule": {"findings": [_finding(code="PYR999")]},
        "unselected-rule": {"rules": {"PYR999": _rule()}},
        "finding-order": {"findings": [_finding(file_name="z.py"), _finding(file_name="a.py")]},
        "suppressed-order": {"suppressed": [_finding(file_name="z.py"), _finding(file_name="a.py")]},
        "error-order": {"errors": [_error(file_name="z.py"), _error(file_name="a.py")]},
        "rule-order": {"rules": {"PYR999": _rule(), "PYR402": _rule()}},
    }
    document.update(examples[case])
    assert _valid(document=document)


@pytest.mark.parametrize(
    "requirement",
    [
        "Every kept or suppressed finding's code has a rules entry.",
        "The rules object contains exactly the selected rules, including those with no findings.",
        "Findings and suppressed findings are ordered by the primary span's",
        "The position key is file_name, line_start, column_start, line_end and column_end.",
        "Errors are ordered by file_name and then line where present. Rules are ordered by code.",
    ],
)
def test_document_records_migration_invariants(*, requirement: str) -> None:
    """The cross-reference and ordering obligations for #269 remain explicit in the schema."""
    invariants = " ".join(cast("list[str]", load_v2_schema()["x-invariants"]))
    assert requirement in invariants


def test_consumer_compatibility_does_not_relax_producer_validation() -> None:
    """New optional fields remain invalid under an old producer schema; consumers parse their known fields."""
    document = copy.deepcopy(_document())
    document["future_optional_field"] = "future"
    assert not _valid(document=document)
    policy = " ".join(cast("list[str]", load_v2_schema()["x-extension-policy"]))
    expected_policy = "rather than validate against an older strict schema"
    assert expected_policy in policy
