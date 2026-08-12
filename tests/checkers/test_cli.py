"""Tests for pyrigor's checker CLI entry point."""

from pathlib import Path

from pytest import CaptureFixture

from pyrigor.checkers.cli import main


def test_main_reports_violation_and_returns_nonzero(  # pyrigor: 402 # pytest fixture injection is positional-only.
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    """A file with a PYR402 violation should be reported and exit non-zero."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def apply_correction(weight, bias):\n    ...\n")

    exit_code = main([str(bad_file)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert f"{bad_file}:1:1: PYR402" in captured.out
    assert "(keyword-only-arguments)" in captured.out


def test_main_does_not_report_suppressed_violation(  # pyrigor 402 pytest fixture injection is positional-only.
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    """A violation suppressed via # pyrigor: comment should not be printed, and the exit code should be 0."""
    suppressed_file = tmp_path / "suppressed.py"
    suppressed_file.write_text("def apply_correction(weight, bias):  # pyrigor: 402\n    ...\n")

    exit_code = main(paths=[str(suppressed_file)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
