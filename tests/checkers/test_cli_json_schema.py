"""JSON schema validation tests for pyrigor's CLI output."""

import json
from pathlib import Path
from typing import cast

import jsonschema
import pytest

# pylint: disable=redefined-outer-name  # Pytest injects the schema fixture into each test.
# noinspection PyProtectedMember
from pyrigor.checkers.cli import main  # pyright: ignore[reportPrivateUsage]

_READ_ERROR = "read_error"


@pytest.fixture
def schema() -> dict[str, object]:  # pyright: ignore[reportReturnType]
    """Load the JSON schema for validation."""
    schema_path = Path(__file__).parents[2] / "schemas" / "pyrigor-diagnostics-v1.json"
    if not schema_path.exists():
        pytest.skip("JSON schema file not found")
    return cast("dict[str, object]", json.loads(schema_path.read_text(encoding="utf-8")))


def _assert_valid_schema(*, document: dict[str, object], schema: dict[str, object]) -> None:
    """Assert that a JSON output document conforms to the published schema."""
    jsonschema.Draft202012Validator(schema).validate(document)  # pyright: ignore[reportUnknownMemberType]


def test_json_output_reports_clean_summary(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object]
) -> None:
    """JSON mode emits one complete document for a clean file."""
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("def apply_correction(*, weight, bias):\n    ...\n")

    assert not main(paths=[str(clean_file)], output_format="json")

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document, schema=schema)
    assert document == {
        "schema_version": 1,
        "diagnostics": [],
        "errors": [],
        "summary": {
            "files_checked": 1,
            "diagnostics": 0,
            "suppressed": 0,
            "suppressed_by_rule": {},
        },
    }


def test_json_output_includes_diagnostic_metadata(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object]
) -> None:
    """JSON mode includes location, rule, context, severity, and fixability."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def apply_correction(weight, bias):\n    ...\n")

    assert main(paths=[str(bad_file)], output_format="json") == 1

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document, schema=schema)
    diagnostic = document["diagnostics"][0]
    assert diagnostic == {
        "file": str(bad_file),
        "location": {
            "start": {"line": 1, "column": 1},
            "end": {"line": 2, "column": 8},
        },
        "code": "PYR402",
        "name": "keyword-only-arguments",
        "message": "Function 'apply_correction' has positional parameters; all parameters should be keyword-only",
        "context": {"kind": "Function", "name": "apply_correction"},
        "severity": "warning",
        "fixability": "safe_fix",
    }


def test_json_output_counts_suppressed_diagnostics(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object]
) -> None:
    """JSON mode excludes suppressed diagnostics and counts them in the summary."""
    suppressed_file = tmp_path / "suppressed.py"
    suppressed_file.write_text("def apply_correction(weight, bias):  # pyrigor 402 # external API\n    ...\n")

    assert not main(paths=[str(suppressed_file)], output_format="json")

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document, schema=schema)
    assert document["diagnostics"] == []
    assert document["summary"]["suppressed"] == 1
    assert document["summary"]["suppressed_by_rule"] == {"PYR402": 1}


def test_json_output_reports_parse_error_without_fake_diagnostic(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object]
) -> None:
    """JSON mode reports syntax failures as errors and keeps stdout valid JSON."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def broken(:\n    pass\n")

    assert not main(paths=[str(bad_file)], output_format="json")

    captured = capsys.readouterr()
    document = json.loads(captured.out)
    error = document["errors"][0]
    _assert_valid_schema(document=document, schema=schema)
    assert (document["diagnostics"], error["file"], error["kind"], str(bad_file) in captured.err) == (
        [],
        str(bad_file),
        "parse_error",
        True,
    )


def test_json_output_reports_read_error(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object]
) -> None:
    """JSON mode reports undecodable files as read errors."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_bytes(b"\xa4 not utf-8")

    assert not main(paths=[str(bad_file)], output_format="json")

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document, schema=schema)
    assert document["errors"][0]["kind"] == _READ_ERROR


def test_json_schema_rejects_non_rule_suppression_keys(*, schema: dict[str, object]) -> None:
    """The published schema restricts the suppression summary keys to PYR codes."""
    with pytest.raises(jsonschema.ValidationError):
        _assert_valid_schema(
            document={
                "schema_version": 1,
                "diagnostics": [],
                "errors": [],
                "summary": {
                    "files_checked": 0,
                    "diagnostics": 0,
                    "suppressed": 1,
                    "suppressed_by_rule": {"not-a-rule": 1},
                },
            },
            schema=schema,
        )


def test_json_location_converts_utf8_byte_columns_to_code_points(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object]
) -> None:
    """JSON locations use character columns for non-ASCII source spans."""
    source_file = tmp_path / "unicode.py"
    source_file.write_text("def bad(a, b):\n    café = 1\n", encoding="utf-8")

    assert main(paths=[str(source_file)], output_format="json") == 1

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document, schema=schema)
    assert document["diagnostics"][0]["location"]["end"] == {"line": 2, "column": 13}
