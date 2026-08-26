"""Tests for pyrigor's checker CLI entry point."""
# test assertions compare against expected literal values by design,
# not a magic-value problem
# pylint: disable=magic-value-comparison

import json
from pathlib import Path

import jsonschema
import pytest

from pyrigor.checkers.cli import main, run

SCHEMA = json.loads((Path(__file__).parents[2] / "schemas" / "pyrigor-diagnostics-v1.json").read_text(encoding="utf-8"))


def _assert_valid_schema(*, document: dict[str, object]) -> None:
    """Assert that a JSON output document conforms to the published schema."""
    jsonschema.Draft202012Validator(SCHEMA).validate(document)


# pyrigor 402 # pytest fixture injection, not a real violation
def test_pyr301_violation_prints_variable_not_function(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A PYR301 violation on an annotated variable should print 'Variable', not the hardcoded 'Function'."""
    (tmp_path / "bad.py").write_text("x: tuple[int, str] = (1, 'a')\n")

    main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    assert "Variable 'x'" in captured.out
    assert "Function 'x'" not in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_main_reports_violation_and_returns_nonzero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A file with a PYR402 violation should be reported and exit non-zero."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def apply_correction(weight, bias):\n    ...\n")

    exit_code = main(paths=[str(bad_file)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert f"{bad_file}:1:1: PYR402" in captured.out
    assert "(keyword-only-arguments)" in captured.out


def test_json_output_reports_clean_summary(*, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """JSON mode emits one complete document for a clean file."""
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("def apply_correction(*, weight, bias):\n    ...\n")

    assert main(paths=[str(clean_file)], output_format="json") == 0

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document)
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


def test_json_output_includes_diagnostic_metadata(*, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """JSON mode includes location, rule, context, severity, and fixability."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def apply_correction(weight, bias):\n    ...\n")

    assert main(paths=[str(bad_file)], output_format="json") == 1

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document)
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


def test_json_output_counts_suppressed_diagnostics(*, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """JSON mode excludes suppressed diagnostics and counts them in the summary."""
    suppressed_file = tmp_path / "suppressed.py"
    suppressed_file.write_text("def apply_correction(weight, bias):  # pyrigor 402 # external API\n    ...\n")

    assert main(paths=[str(suppressed_file)], output_format="json") == 0

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document)
    assert document["diagnostics"] == []
    assert document["summary"]["suppressed"] == 1
    assert document["summary"]["suppressed_by_rule"] == {"PYR402": 1}


def test_json_output_reports_parse_error_without_fake_diagnostic(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """JSON mode reports syntax failures as errors and keeps stdout valid JSON."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def broken(:\n    pass\n")

    assert main(paths=[str(bad_file)], output_format="json") == 0

    captured = capsys.readouterr()
    document = json.loads(captured.out)
    error = document["errors"][0]
    _assert_valid_schema(document=document)
    assert (document["diagnostics"], error["file"], error["kind"], str(bad_file) in captured.err) == (
        [],
        str(bad_file),
        "parse_error",
        True,
    )


def test_json_output_reports_read_error(*, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """JSON mode reports undecodable files as read errors."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_bytes(b"\xa4 not utf-8")

    assert main(paths=[str(bad_file)], output_format="json") == 0

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document)
    assert document["errors"][0]["kind"] == "read_error"


def test_json_schema_rejects_non_rule_suppression_keys() -> None:
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
            }
        )


def test_json_location_converts_utf8_byte_columns_to_code_points(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """JSON locations use character columns for non-ASCII source spans."""
    source_file = tmp_path / "unicode.py"
    source_file.write_text("def bad(a, b):\n    café = 1\n", encoding="utf-8")

    assert main(paths=[str(source_file)], output_format="json") == 1

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document)
    assert document["diagnostics"][0]["location"]["end"] == {"line": 2, "column": 13}


# pyrigor 402 # pytest fixture injection, not a real violation
def test_main_does_not_report_suppressed_violation(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A violation suppressed via # pyrigor comment should not be printed as a violation.

    The exit code should be 0.
    """
    suppressed_file = tmp_path / "suppressed.py"
    suppressed_file.write_text("def apply_correction(weight, bias):  # pyrigor 402 # positional swap risk\n    ...\n")

    exit_code = main(paths=[str(suppressed_file)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "apply_correction" not in captured.out
    assert "PYR402: 1 suppressed" in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_delegates_to_main_using_sys_argv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run() should parse sys.argv and pass it to main(), exiting with its return code."""
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("def apply_correction(*, weight, bias):\n    ...\n")

    monkeypatch.setattr("sys.argv", ["pyrigor", str(clean_file)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 0


def test_run_accepts_repeated_exclude_flags(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """run() should pass every repeated --exclude path to the file collector."""
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    first.write_text("def one(a, b):\n    ...\n")
    second.write_text("def two(a, b):\n    ...\n")
    monkeypatch.setattr("sys.argv", ["pyrigor", "--exclude", str(first), "--exclude", str(second), str(tmp_path)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 0
    assert "Checked 0 files" in capsys.readouterr().out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_output_format_json_emits_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """run() should pass '--output-format=json' through to the CLI."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def apply_correction(weight, bias):\n    ...\n")
    monkeypatch.setattr("sys.argv", ["pyrigor", "--output-format=json", str(bad_file)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 1
    assert json.loads(capsys.readouterr().out)["diagnostics"][0]["code"] == "PYR402"


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_output_format_accepts_space_form(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """run() should accept the space-separated --output-format form."""
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("x = 1\n")
    monkeypatch.setattr("sys.argv", ["pyrigor", "--output-format", "json", str(clean_file)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 0
    assert json.loads(capsys.readouterr().out)["diagnostics"] == []


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_output_format_human_remains_human(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Explicit human output should retain the existing text format."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def apply_correction(weight, bias):\n    ...\n")
    monkeypatch.setattr("sys.argv", ["pyrigor", "--output-format=human", str(bad_file)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "PYR402" in captured.out
    with pytest.raises(json.JSONDecodeError):
        json.loads(captured.out)


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_output_format_combines_with_filters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """JSON output should respect both select and ignore filters."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n")
    monkeypatch.setattr(
        "sys.argv", ["pyrigor", "--output-format=json", "--select=PYR401", "--ignore=PYR402", str(bad_file)]
    )

    with pytest.raises(SystemExit) as exc_info:
        run()

    document = json.loads(capsys.readouterr().out)
    assert exc_info.value.code == 1
    assert [diagnostic["code"] for diagnostic in document["diagnostics"]] == ["PYR401"]


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_output_format_rejects_invalid_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unsupported output format should fail during argument parsing."""
    monkeypatch.setattr("sys.argv", ["pyrigor", "--output-format=xml", str(tmp_path)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 2


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_output_format_requires_a_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing output-format value should fail during argument parsing."""
    monkeypatch.setattr("sys.argv", ["pyrigor", "--output-format", str(tmp_path)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 2


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_output_format_rejects_repeated_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A repeated output-format flag should fail instead of silently choosing one."""
    monkeypatch.setattr("sys.argv", ["pyrigor", "--output-format=json", "--output-format=human", str(tmp_path)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 2
    assert "--output-format" in capsys.readouterr().err


# pyrigor 402 # pytest fixture injection, not a real violation
def test_main_walks_a_directory_for_python_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Passing a directory should recursively find and check every .py file inside it."""
    (tmp_path / "bad.py").write_text("def apply_correction(weight, bias):\n    ...\n")
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "also_bad.py").write_text("def another(a, b):\n    ...\n")

    exit_code = main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "bad.py" in captured.out
    assert "also_bad.py" in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_directory_walk_excludes_venv(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Files inside a .venv directory should be excluded from the walk."""
    (tmp_path / "real.py").write_text("def apply_correction(weight, bias):\n    ...\n")
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    (venv_dir / "vendored.py").write_text("def another(a, b):\n    ...\n")

    exit_code = main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "real.py" in captured.out
    assert "vendored.py" not in captured.out


def test_main_excludes_user_selected_directory(*, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--exclude should omit files below an excluded directory."""
    included = tmp_path / "included.py"
    included.write_text("def apply_correction(weight, bias):\n    ...\n")
    excluded_dir = tmp_path / "generated"
    excluded_dir.mkdir()
    (excluded_dir / "excluded.py").write_text("def another(a, b):\n    ...\n")

    assert main(paths=[str(tmp_path)], excludes=[str(excluded_dir)]) == 1
    captured = capsys.readouterr()
    assert "included.py" in captured.out
    assert "excluded.py" not in captured.out


def test_main_excludes_explicit_file(*, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--exclude should omit an explicitly supplied file too."""
    excluded = tmp_path / "excluded.py"
    excluded.write_text("def apply_correction(weight, bias):\n    ...\n")

    assert main(paths=[str(excluded)], excludes=[str(excluded)]) == 0
    assert "Checked 0 files" in capsys.readouterr().out


def test_main_combines_file_and_directory_exclusions(*, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Multiple exclusions should combine without affecting remaining files."""
    keep = tmp_path / "keep.py"
    excluded_file = tmp_path / "excluded.py"
    excluded_dir = tmp_path / "generated"
    excluded_dir.mkdir()
    keep.write_text("def keep(*, value):\n    ...\n")
    excluded_file.write_text("def excluded(a, b):\n    ...\n")
    nested = excluded_dir / "nested.py"
    nested.write_text("def nested(a, b):\n    ...\n")

    assert main(paths=[str(tmp_path)], excludes=[str(excluded_file), str(excluded_dir), str(excluded_dir)]) == 0
    captured = capsys.readouterr()
    assert "Checked 1 file" in captured.out
    assert "excluded.py" not in captured.out
    assert "nested.py" not in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_main_prints_timing_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """main() should print how many files were checked and how long it took."""
    (tmp_path / "clean.py").write_text("def apply_correction(*, weight, bias):\n    ...\n")

    main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    assert "1 file" in captured.out
    assert "s" in captured.out  # seconds unit present somewhere in the summary


# pyrigor 403 # pytest fixture injection, not a real violation
def test_check_file_handles_bom(tmp_path: Path) -> None:
    """A file with a UTF-8 Byte Order Mark (BOM) should be parsed correctly, not crash."""
    bom_file = tmp_path / "bom.py"
    bom_file.write_bytes("def apply_correction(*, weight, bias):\n    ...\n".encode("utf-8-sig"))

    exit_code = main(paths=[str(bom_file)])

    assert exit_code == 0


# pyrigor 402 # pytest fixture injection, not a real violation
def test_directory_walk_excludes_site_packages(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Files inside any site-packages directory should be excluded, regardless of the venv folder's own name."""
    (tmp_path / "real.py").write_text("def apply_correction(*, weight, bias):\n    ...\n")
    weird_venv = tmp_path / ".venv_old_py314" / "Lib" / "site-packages" / "somelib"
    weird_venv.mkdir(parents=True)
    (weird_venv / "vendored.py").write_text("def another(a, b):\n    ...\n")

    main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    assert "vendored.py" not in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_overlapping_file_and_directory_args_check_file_once(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A file reachable via both a relative arg and an absolute containing-directory arg is checked once."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def apply_correction(weight, bias):\n    ...\n")
    monkeypatch.chdir(tmp_path)

    exit_code = main(paths=["bad.py", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Checked 1 file in" in captured.out
    assert "PYR402: 1" in captured.out
    assert "PYR402: 2" not in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_unreadable_file_is_skipped_with_warning(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A file that cannot be decoded or parsed should be skipped with a warning, not crash the run."""
    bad_file = tmp_path / "bad_encoding.py"
    bad_file.write_bytes(b"\xa4\xa4 not valid utf-8 at all")
    good_file = tmp_path / "good.py"
    good_file.write_text("def apply_correction(*, weight, bias):\n    ...\n")

    exit_code = main(paths=[str(bad_file), str(good_file)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "bad_encoding.py" in captured.err


# pyrigor 402 # pytest fixture injection, not a real violation
def test_unparseable_file_is_skipped_with_warning(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A file with invalid Python syntax should be skipped with a warning, not crash the run."""
    bad_syntax_file = tmp_path / "bad_syntax.py"
    bad_syntax_file.write_text("def broken(:\n    pass\n")

    exit_code = main(paths=[str(bad_syntax_file)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "bad_syntax.py" in captured.err


# pyrigor 402 # pytest fixture injection, not a real violation
def test_main_prints_violation_count(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The summary line should include a total violation count."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n\ndef two(c, d):\n    ...\n")

    main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    assert "2 violations" in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_prints_version_and_exits(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """run() with --version should print the installed version and exit 0, without checking any files."""
    monkeypatch.setattr("sys.argv", ["pyrigor", "--version"])

    with pytest.raises(SystemExit) as exc_info:
        run()

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert "pyrigor" in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_main_prints_per_rule_breakdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The summary should break violations down by rule."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n")

    main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    assert "PYR401: 1" in captured.out
    assert "PYR402: 1" in captured.out


# pyrigor 403 # pytest fixture injection, not a real violation
def test_run_returns_2_on_unexpected_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unexpected exception in main() should exit 2, not 1, distinguishing a real crash from violations found."""

    # noinspection PyUnusedLocal
    def _boom(*, paths: list[str], select: set[str] | None, ignore: set[str] | None, excludes: list[str] | None) -> int:
        # Must accept the same keywords as main()'s real call site
        # (main (paths=args.paths, select=select, ignore=ignore)), or a
        # TypeError is raised instead of the intended RuntimeError, still
        # caught by the same except Exception handler but not exercising
        # the real crash path.
        del paths, select, ignore, excludes
        raise RuntimeError("something genuinely broke")

    monkeypatch.setattr("pyrigor.checkers.cli.main", _boom)
    monkeypatch.setattr("sys.argv", ["pyrigor", "some_path"])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 2


# pyrigor 402 # pytest fixture injection, not a real violation
def test_main_prints_per_file_breakdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The summary should list each file's own violation count."""
    (tmp_path / "bad_a.py").write_text("def one(a, b):\n    ...\n")
    (tmp_path / "bad_b.py").write_text("def two(c, d):\n    ...\n\ndef three(e, f):\n    ...\n")

    main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    assert "bad_a.py: 1" in captured.out
    assert "bad_b.py: 2" in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_per_file_breakdown_skips_clean_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A clean file, with no violations, should not appear in the per-file breakdown."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n")
    (tmp_path / "clean.py").write_text("def two(*, a, b):\n    ...\n")

    main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    assert "bad.py: 1" in captured.out
    assert "clean.py" not in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_summary_line_prints_after_per_rule_and_per_file_breakdown(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The 'Checked N files...' totals line should print last, after the breakdowns, not first."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n")
    main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    summary_index = captured.out.index("Checked 1 file")
    per_file_index = captured.out.index("bad.py: 1")

    assert per_file_index < summary_index


# pyrigor 402 # pytest fixture injection, not a real violation
def test_per_rule_breakdown_prints_after_per_file_breakdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The per-rule breakdown should print after the per-file breakdown, not before it."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n")

    main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    per_file_index = captured.out.index("bad.py: 1")
    per_rule_index = captured.out.index("PYR402: 1")

    assert per_file_index < per_rule_index


# pyrigor 402 # pytest fixture injection, not a real violation
def test_summary_aggregates_multiple_suppressions_under_same_rule(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Multiple suppressed violations under the same rule should sum correctly in the summary."""
    (tmp_path / "a.py").write_text("def one(a, b):  # pyrigor 402 # matches a fixed external API\n    ...\n")
    (tmp_path / "b.py").write_text("def two(c, d):  # pyrigor 402 # matches a fixed external API\n    ...\n")

    main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    assert "PYR402: 2 suppressed" in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_main_select_runs_specified_rule(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """With select={"PYR401"}, only PYR401 violations should be reported, even if others exist."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n")

    main(paths=[str(tmp_path)], select={"PYR401"})

    captured = capsys.readouterr()
    assert "PYR401" in captured.out
    assert "PYR402" not in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_parses_select_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """run() should parse --select=CODE, CODE out of argv and pass it to main()."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n")
    monkeypatch.setattr("sys.argv", ["pyrigor", "--select=PYR401", str(tmp_path)])

    with pytest.raises(SystemExit):
        run()

    captured = capsys.readouterr()
    assert "PYR401" in captured.out
    assert "PYR402" not in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_main_select_accepts_symbolic_name(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--select should accept a rule's symbolic-name, not just its code."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n")

    main(paths=[str(tmp_path)], select={"namedtuple-returns"})

    captured = capsys.readouterr()
    assert "PYR401" in captured.out
    assert "PYR402" not in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_select_flag_tolerates_whitespace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--select=CODE, CODE with a space after the comma should still work."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n")
    monkeypatch.setattr("sys.argv", ["pyrigor", "--select=PYR401, PYR402", str(tmp_path)])

    with pytest.raises(SystemExit):
        run()

    captured = capsys.readouterr()
    assert "PYR401" in captured.out
    assert "PYR402" in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_main_select_accepts_bare_number_shorthand(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--select should accept a rule's bare number, not just its full code."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n")

    main(paths=[str(tmp_path)], select={"401"})

    captured = capsys.readouterr()
    assert "PYR401" in captured.out
    assert "PYR402" not in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_select_flag_errors_on_unknown_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--select with an unrecognized code should error immediately, not silently run zero checkers."""
    monkeypatch.setattr("sys.argv", ["pyrigor", "--select=PYR999", str(tmp_path)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "PYR999" in captured.err
    assert "unknown" in captured.err.lower()


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_select_flag_errors_on_repeated_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A second --select= flag should error immediately, not get treated as a path."""
    monkeypatch.setattr("sys.argv", ["pyrigor", "--select=PYR401", "--select=PYR402", str(tmp_path)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "--select" in captured.err


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_select_flag_errors_on_three_repeated_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """More than two --select= flags should still error, not just exactly two."""
    monkeypatch.setattr(
        "sys.argv",
        ["pyrigor", "--select=PYR401", "--select=PYR402", "--select=PYR403", str(tmp_path)],
    )

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 2


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_select_flag_errors_on_repeated_identical_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two --select= flags with the same value should still error, not just when they disagree."""
    monkeypatch.setattr("sys.argv", ["pyrigor", "--select=PYR401", "--select=PYR401", str(tmp_path)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 2


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_select_flag_errors_on_repeated_flag_before_processing_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The repeated-flag error should fire before any file is checked, not after a partial run."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n")
    monkeypatch.setattr("sys.argv", ["pyrigor", "--select=PYR401", "--select=PYR402", str(tmp_path)])

    with pytest.raises(SystemExit):
        run()

    captured = capsys.readouterr()
    assert "Checked" not in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_unrecognized_flag_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A genuine unrecognized flag (a typo) should error immediately, not be silently treated as a path."""
    monkeypatch.setattr("sys.argv", ["pyrigor", "--onl=PYR401", str(tmp_path)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 2


# pyrigor 403 # pytest fixture injection, not a real violation
def test_run_no_paths_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Running with no path arguments at all should error, not silently check zero files."""
    monkeypatch.setattr("sys.argv", ["pyrigor"])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 2


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_select_swallowing_path_prints_a_hint(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--select PATH (space form, no real code) should hint that PATH was consumed as '--select's' value.

    A valid --ignore=CODE precedes it, so the hint scan must skip past a
    non-culprit token before finding the actual swallowed value.
    """
    monkeypatch.setattr("sys.argv", ["pyrigor", "--ignore=PYR401", "--select", ".\\pyrigor\\"])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "'.\\pyrigor\\' was consumed as --select's value" in captured.err
    assert "--select=PYR401" in captured.err
    assert "the following arguments are required: paths" in captured.err


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_select_flag_accepts_space_separated_form(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--select PYR401 (space-separated, not --select=PYR401) should now work."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n")
    monkeypatch.setattr("sys.argv", ["pyrigor", "--select", "PYR401", str(tmp_path)])

    with pytest.raises(SystemExit):
        run()

    captured = capsys.readouterr()
    assert "PYR401" in captured.out
    assert "PYR402" not in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_short_version_flag_prints_version_and_exits(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """run() with -V (the short form) should behave identically to --version."""
    monkeypatch.setattr("sys.argv", ["pyrigor", "-V"])

    with pytest.raises(SystemExit) as exc_info:
        run()

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert "pyrigor" in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_version_flag_overrides_missing_path_and_other_flags(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--version should short-circuit before --select is validated or paths are required, in either order."""
    monkeypatch.setattr("sys.argv", ["pyrigor", "--select", "403", "--version"])

    with pytest.raises(SystemExit) as exc_info:
        run()

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert "pyrigor" in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_ignore_only_excludes_from_full_rule_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--ignore alone should exclude the given rule but still run every other one."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n")
    monkeypatch.setattr("sys.argv", ["pyrigor", "--ignore=PYR402", str(tmp_path)])

    with pytest.raises(SystemExit):
        run()

    captured = capsys.readouterr()
    assert "PYR401" in captured.out
    assert "PYR402" not in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_ignore_flag_accepts_symbolic_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--ignore should accept a rule's symbolic name, not just its code."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n")
    monkeypatch.setattr("sys.argv", ["pyrigor", "--ignore=keyword-only-arguments", str(tmp_path)])

    with pytest.raises(SystemExit):
        run()

    captured = capsys.readouterr()
    assert "PYR401" in captured.out
    assert "PYR402" not in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_ignore_flag_accepts_space_separated_form(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--ignore PYR402 (space-separated, not --ignore=PYR402) should work."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n")
    monkeypatch.setattr("sys.argv", ["pyrigor", "--ignore", "PYR402", str(tmp_path)])

    with pytest.raises(SystemExit):
        run()

    captured = capsys.readouterr()
    assert "PYR401" in captured.out
    assert "PYR402" not in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_ignore_flag_errors_on_unknown_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--ignore with an unrecognized code should error immediately, using --ignore in the message."""
    monkeypatch.setattr("sys.argv", ["pyrigor", "--ignore=PYR999", str(tmp_path)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "PYR999" in captured.err
    assert "--ignore" in captured.err
    assert "unknown" in captured.err.lower()


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_ignore_flag_errors_on_repeated_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A second --ignore= flag should error immediately, using --ignore in the message."""
    monkeypatch.setattr("sys.argv", ["pyrigor", "--ignore=PYR401", "--ignore=PYR402", str(tmp_path)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "--ignore" in captured.err


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_select_and_ignore_combine_with_partial_overlap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--select and --ignore together should start from '--select's' set and remove '--ignore's' codes."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n")
    monkeypatch.setattr("sys.argv", ["pyrigor", "--select=PYR401,PYR402", "--ignore=PYR402", str(tmp_path)])

    with pytest.raises(SystemExit):
        run()

    captured = capsys.readouterr()
    assert "PYR401" in captured.out
    assert "PYR402" not in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_select_and_ignore_order_does_not_matter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--ignore given before --select should combine identically to --select given first."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n")
    monkeypatch.setattr("sys.argv", ["pyrigor", "--ignore=PYR402", "--select=PYR401,PYR402", str(tmp_path)])

    with pytest.raises(SystemExit):
        run()

    captured = capsys.readouterr()
    assert "PYR401" in captured.out
    assert "PYR402" not in captured.out


# pyrigor 402 # pytest fixture injection, not a real violation
def test_run_select_and_ignore_full_overlap_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--select and --ignore naming the same rule should error, not silently check zero rules."""
    monkeypatch.setattr("sys.argv", ["pyrigor", "--select=403", "--ignore=403", str(tmp_path)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "no rules to check" in captured.err.lower()
