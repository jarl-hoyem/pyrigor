"""Tests for pyrigor's checker CLI entry point."""

from pathlib import Path

import pytest
from pytest import CaptureFixture

from pyrigor.checkers.cli import main, run


def test_main_reports_violation_and_returns_nonzero(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """A file with a PYR402 violation should be reported and exit non-zero."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def apply_correction(weight, bias):\n    ...\n")

    exit_code = main([str(bad_file)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert f"{bad_file}:1:1: PYR402" in captured.out
    assert "(keyword-only-arguments)" in captured.out


def test_main_does_not_report_suppressed_violation(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """A violation suppressed via # pyrigor: comment should not be printed, and the exit code should be 0."""
    suppressed_file = tmp_path / "suppressed.py"
    suppressed_file.write_text("def apply_correction(weight, bias):  # pyrigor: 402 # positional swap risk\n    ...\n")

    exit_code = main(paths=[str(suppressed_file)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "PYR402" not in captured.out
    assert "Checked 1 file" in captured.out


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
