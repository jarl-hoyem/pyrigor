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
