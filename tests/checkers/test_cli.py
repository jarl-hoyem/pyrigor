"""Tests for pyrigor's checker CLI entry point."""

from pathlib import Path

import pytest
from pytest import CaptureFixture

from pyrigor.checkers.cli import main, run


def test_main_reports_violation_and_returns_nonzero(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """A file with a PYR402 violation should be reported and exit non-zero."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def apply_correction(weight, bias):\n    ...\n")

    exit_code = main(paths=[str(bad_file)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert f"{bad_file}:1:1: PYR402" in captured.out
    assert "(keyword-only-arguments)" in captured.out


def test_main_does_not_report_suppressed_violation(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """A violation suppressed via # pyrigor: comment should not be printed as a violation.

    The exit code should be 0.
    """
    suppressed_file = tmp_path / "suppressed.py"
    suppressed_file.write_text("def apply_correction(weight, bias):  # pyrigor: 402 # positional swap risk\n    ...\n")

    exit_code = main(paths=[str(suppressed_file)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "apply_correction" not in captured.out
    assert "PYR402: 1 suppressed" in captured.out


def test_run_delegates_to_main_using_sys_argv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run() should parse sys.argv and pass it to main(), exiting with its return code."""
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("def apply_correction(*, weight, bias):\n    ...\n")

    monkeypatch.setattr("sys.argv", ["pyrigor", str(clean_file)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 0


def test_main_walks_a_directory_for_python_files(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
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


def test_directory_walk_excludes_venv(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
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


def test_main_prints_timing_summary(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """main() should print how many files were checked and how long it took."""
    (tmp_path / "clean.py").write_text("def apply_correction(*, weight, bias):\n    ...\n")

    main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    assert "1 file" in captured.out
    assert "s" in captured.out  # seconds unit present somewhere in the summary


def test_check_file_handles_bom(tmp_path: Path) -> None:
    """A file with a UTF-8 Byte Order Mark (BOM) should be parsed correctly, not crash."""
    bom_file = tmp_path / "bom.py"
    bom_file.write_bytes("def apply_correction(*, weight, bias):\n    ...\n".encode("utf-8-sig"))

    exit_code = main(paths=[str(bom_file)])

    assert exit_code == 0


def test_directory_walk_excludes_site_packages(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """Files inside any site-packages directory should be excluded, regardless of the venv folder's own name."""
    (tmp_path / "real.py").write_text("def apply_correction(*, weight, bias):\n    ...\n")
    weird_venv = tmp_path / ".venv_old_py314" / "Lib" / "site-packages" / "somelib"
    weird_venv.mkdir(parents=True)
    (weird_venv / "vendored.py").write_text("def another(a, b):\n    ...\n")

    main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    assert "vendored.py" not in captured.out


def test_unreadable_file_is_skipped_with_warning(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """A file that cannot be decoded or parsed should be skipped with a warning, not crash the run."""
    bad_file = tmp_path / "bad_encoding.py"
    bad_file.write_bytes(b"\xa4\xa4 not valid utf-8 at all")
    good_file = tmp_path / "good.py"
    good_file.write_text("def apply_correction(*, weight, bias):\n    ...\n")

    exit_code = main(paths=[str(bad_file), str(good_file)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "bad_encoding.py" in captured.err


def test_unparseable_file_is_skipped_with_warning(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """A file with invalid Python syntax should be skipped with a warning, not crash the run."""
    bad_syntax_file = tmp_path / "bad_syntax.py"
    bad_syntax_file.write_text("def broken(:\n    pass\n")

    exit_code = main(paths=[str(bad_syntax_file)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "bad_syntax.py" in captured.err


def test_main_prints_violation_count(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """The summary line should include a total violation count."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n\ndef two(c, d):\n    ...\n")

    main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    assert "2 violations" in captured.out


def test_run_prints_version_and_exits(monkeypatch: pytest.MonkeyPatch, capsys: CaptureFixture[str]) -> None:
    """run() with --version should print the installed version and exit 0, without checking any files."""
    monkeypatch.setattr("sys.argv", ["pyrigor", "--version"])

    with pytest.raises(SystemExit) as exc_info:
        run()

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert "pyrigor" in captured.out


def test_main_prints_per_rule_breakdown(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """The summary should break violations down by rule."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n")

    main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    assert "PYR401: 1" in captured.out
    assert "PYR402: 1" in captured.out


def test_run_returns_2_on_unexpected_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unexpected exception in main() should exit 2, not 1, distinguishing a real crash from violations found."""

    # noinspection PyUnusedLocal
    def _boom(*, paths: list[str]) -> int:
        # Must keep this exact name to match main()'s real call site
        # (main(paths=args, ...)). The del statement marks it used so vulture doesn't
        # flag it as an unused parameter.
        del paths
        raise RuntimeError("something genuinely broke")

    monkeypatch.setattr("pyrigor.checkers.cli.main", _boom)

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 2


def test_main_prints_per_file_breakdown(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """The summary should list each file's own violation count."""
    (tmp_path / "bad_a.py").write_text("def one(a, b):\n    ...\n")
    (tmp_path / "bad_b.py").write_text("def two(c, d):\n    ...\n\ndef three(e, f):\n    ...\n")

    main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    assert "bad_a.py: 1" in captured.out
    assert "bad_b.py: 2" in captured.out


def test_per_file_breakdown_skips_clean_files(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """A clean file, with no violations, should not appear in the per-file breakdown."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n")
    (tmp_path / "clean.py").write_text("def two(*, a, b):\n    ...\n")

    main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    assert "bad.py: 1" in captured.out
    assert "clean.py" not in captured.out


def test_summary_line_prints_after_per_rule_and_per_file_breakdown(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """The 'Checked N files...' totals line should print last, after the breakdowns, not first."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n")

    main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    summary_index = captured.out.index("Checked 1 file")
    per_file_index = captured.out.index("bad.py: 1")

    assert per_file_index < summary_index


def test_per_rule_breakdown_prints_after_per_file_breakdown(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """The per-rule breakdown should print after the per-file breakdown, not before it."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n")

    main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    per_file_index = captured.out.index("bad.py: 1")
    per_rule_index = captured.out.index("PYR402: 1")

    assert per_file_index < per_rule_index


def test_summary_aggregates_multiple_suppressions_under_same_rule(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """Multiple suppressed violations under the same rule should sum correctly in the summary."""
    (tmp_path / "a.py").write_text("def one(a, b):  # pyrigor: 402 # matches a fixed external API\n    ...\n")
    (tmp_path / "b.py").write_text("def two(c, d):  # pyrigor: 402 # matches a fixed external API\n    ...\n")

    main(paths=[str(tmp_path)])

    captured = capsys.readouterr()
    assert "PYR402: 2 suppressed" in captured.out


def test_main_only_runs_specified_rule(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """With only={"PYR401"}, only PYR401 violations should be reported, even if others exist."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n")

    main(paths=[str(tmp_path)], only={"PYR401"})

    captured = capsys.readouterr()
    assert "PYR401" in captured.out
    assert "PYR402" not in captured.out


def test_run_parses_only_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: CaptureFixture[str]) -> None:
    """run() should parse --only=CODE, CODE out of argv and pass it to main()."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n")
    monkeypatch.setattr("sys.argv", ["pyrigor", "--only=PYR401", str(tmp_path)])

    with pytest.raises(SystemExit):
        run()

    captured = capsys.readouterr()
    assert "PYR401" in captured.out
    assert "PYR402" not in captured.out


def test_main_only_accepts_symbolic_name(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """--only should accept a rule's symbolic-name, not just its code."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n")

    main(paths=[str(tmp_path)], only={"namedtuple-returns"})

    captured = capsys.readouterr()
    assert "PYR401" in captured.out
    assert "PYR402" not in captured.out


def test_run_only_flag_tolerates_whitespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    """--only=CODE, CODE with a space after the comma should still work."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n")
    monkeypatch.setattr("sys.argv", ["pyrigor", "--only=PYR401, PYR402", str(tmp_path)])

    with pytest.raises(SystemExit):
        run()

    captured = capsys.readouterr()
    assert "PYR401" in captured.out
    assert "PYR402" in captured.out


def test_main_only_accepts_bare_number_shorthand(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """--only should accept a rule's bare number, not just its full code."""
    (tmp_path / "bad.py").write_text("def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n")

    main(paths=[str(tmp_path)], only={"401"})

    captured = capsys.readouterr()
    assert "PYR401" in captured.out
    assert "PYR402" not in captured.out


def test_run_only_flag_errors_on_unknown_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    """--only with an unrecognized code should error immediately, not silently run zero checkers."""
    monkeypatch.setattr("sys.argv", ["pyrigor", "--only=PYR999", str(tmp_path)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "PYR999" in captured.err
    assert "unknown" in captured.err.lower()
