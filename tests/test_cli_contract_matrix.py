"""Contract tests for the installed pyrigor CLI."""

import json
import os
import subprocess  # nosec B404 -- tests invoke the fixed installed pyrigor entry point
import sys
from pathlib import Path
from typing import cast

_WINDOWS_OS_NAME = "nt"
_SUCCESS_EXIT_CODE = 0
_USAGE_ERROR_EXIT_CODE = 2
_NO_VIOLATIONS = "0 violations"
_EMPTY_RULE_SELECTION_ERROR = "--select and --ignore combine to leave no rules to check"
_REPEATED_OUTPUT_FORMAT_ERROR = "--output-format can only be given once"
_JSON_OPTION = "--output-format=json"
_CLI_NAME = "pyrigor.exe" if os.name == _WINDOWS_OS_NAME else "pyrigor"


def _installed_cli() -> str:
    """Return the installed pyrigor entry point for this test environment."""
    executable = Path(sys.executable).parent / _CLI_NAME
    assert executable.is_file(), f"Installed pyrigor entry point not found: {executable}"
    return str(executable)


def _run_cli(*, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a fixed CLI command and capture its output."""
    # noinspection PyArgumentEqualDefault
    return subprocess.run(  # nosec B603 -- executes the fixed installed pyrigor entry point # noqa: S603
        [_installed_cli(), *arguments],
        capture_output=True,
        check=False,
        text=True,
    )


def _json_document(*, result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    """Parse the JSON document emitted by the CLI."""
    document = json.loads(result.stdout)
    assert isinstance(document, dict)
    # PyCharm rejects valid quoted cast types required by Ruff TC006.
    return cast("dict[str, object]", document)  # type: ignore[pycharm:PyTypeChecker, unused-ignore]


def test_installed_cli_reports_clean_file(*, tmp_path: Path) -> None:
    """A clean file exits successfully through the installed entry point."""
    source = tmp_path / "clean.py"
    source.write_text("def clean(*, value):\n    return value\n", encoding="utf-8")

    result = _run_cli(arguments=[str(source)])

    assert result.returncode == _SUCCESS_EXIT_CODE
    assert _NO_VIOLATIONS in result.stdout


def test_installed_cli_reports_json_diagnostic(*, tmp_path: Path) -> None:
    """A violation has a schema-valid JSON diagnostic through the installed CLI."""
    source = tmp_path / "violation.py"
    source.write_text("def apply(left, right):\n    return left + right\n", encoding="utf-8")

    result = _run_cli(arguments=[_JSON_OPTION, str(source)])

    document = _json_document(result=result)
    # PyCharm rejects valid quoted cast types required by Ruff TC006.
    value = document["diagnostics"]
    diagnostics = cast("list[dict[str, object]]", value)  # type: ignore[pycharm:PyTypeChecker, unused-ignore]
    assert result.returncode == 1
    assert document["schema_version"] == 1
    assert [diagnostic["code"] for diagnostic in diagnostics] == ["PYR402"]


def test_installed_cli_reports_suppressed_diagnostic(*, tmp_path: Path) -> None:
    """A suppressed violation is absent from diagnostics but present in the summary."""
    source = tmp_path / "suppressed.py"
    source.write_text(
        "def apply(left, right):  # pyrigor PYR402 # external API\n    return left + right\n",
        encoding="utf-8",
    )

    result = _run_cli(arguments=[_JSON_OPTION, str(source)])

    document = _json_document(result=result)
    # PyCharm rejects valid quoted cast types required by Ruff TC006.
    summary = cast("dict[str, object]", document["summary"])  # type: ignore[pycharm:PyTypeChecker, unused-ignore]
    assert result.returncode == _SUCCESS_EXIT_CODE
    assert document["diagnostics"] == []
    assert summary["suppressed"] == 1
    assert summary["suppressed_by_rule"] == {"PYR402": 1}


def test_installed_cli_reports_parse_error(*, tmp_path: Path) -> None:
    """Malformed Python appears as a structured parse error."""
    source = tmp_path / "broken.py"
    source.write_text("def broken(:\n    pass\n", encoding="utf-8")

    result = _run_cli(arguments=[_JSON_OPTION, str(source)])

    document = _json_document(result=result)
    # PyCharm rejects valid quoted cast types required by Ruff TC006.
    errors = cast("list[dict[str, object]]", document["errors"])  # type: ignore[pycharm:PyTypeChecker, unused-ignore]
    assert result.returncode == _SUCCESS_EXIT_CODE
    assert [error["kind"] for error in errors] == ["parse_error"]


def test_installed_cli_rejects_empty_rule_selection(*, tmp_path: Path) -> None:
    """Conflicting select and ignore options leave no rules to check."""
    source = tmp_path / "violation.py"
    source.write_text("def apply(left, right):\n    return left + right\n", encoding="utf-8")

    result = _run_cli(arguments=["--select=PYR402", "--ignore=PYR402", str(source)])

    assert result.returncode == _USAGE_ERROR_EXIT_CODE
    assert _EMPTY_RULE_SELECTION_ERROR in result.stderr


def test_installed_cli_rejects_repeated_output_format(*, tmp_path: Path) -> None:
    """Repeated output-format options are rejected before checking files."""
    source = tmp_path / "clean.py"
    source.write_text("def clean(*, value):\n    return value\n", encoding="utf-8")

    result = _run_cli(arguments=[_JSON_OPTION, "--output-format=human", str(source)])

    assert result.returncode == _USAGE_ERROR_EXIT_CODE
    assert _REPEATED_OUTPUT_FORMAT_ERROR in result.stderr
