"""Tests for pyrigor's checker CLI entry point."""

from pathlib import Path

from pytest import CaptureFixture

from pyrigor.checkers.cli import main


def test_main_reports_violation_and_returns_nonzero(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """A file with a PYR003 violation should be reported and exit non-zero."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def apply_correction(weight, bias):\n    ...\n")

    exit_code = main([str(bad_file)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert f"{bad_file}:1:1: PYR003" in captured.out
