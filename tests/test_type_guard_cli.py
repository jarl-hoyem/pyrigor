"""End-to-end tests of the TypeGuard and TypeIs exemption through the command line."""
# test assertions compare against expected literal values by design,
# not a magic-value problem

from pathlib import Path
from typing import Final

import pytest

from pyrigor.checkers.cli import run

_PYR402: Final = "PYR402"
_PYR403: Final = "PYR403"
_GUARD_WITH_EXTRA = "def is_int(value, strict) -> TypeGuard[int]:\n    ...\n"
_GUARD_FIXED = "def is_int(value, *, strict) -> TypeGuard[int]:\n    ...\n"


def test_scan_accepts_a_lone_guard_parameter(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A guard with only its narrowed value is clean under both rules."""
    source_file = tmp_path / "source.py"
    source_file.write_text("def is_int(value) -> TypeGuard[int]:\n    ...\n")

    monkeypatch.setattr("sys.argv", ["pyrigor", "--select=PYR402,PYR403", str(source_file)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert not exc_info.value.code
    output = capsys.readouterr().out
    assert _PYR402 not in output
    assert _PYR403 not in output


def test_scan_still_reports_a_further_positional_parameter(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A positional parameter after the narrowed value is still reported as PYR402."""
    source_file = tmp_path / "source.py"
    source_file.write_text(_GUARD_WITH_EXTRA)

    monkeypatch.setattr("sys.argv", ["pyrigor", "--select=PYR402,PYR403", str(source_file)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    output = capsys.readouterr().out
    assert exc_info.value.code
    assert _PYR402 in output
    assert _PYR403 not in output


def test_fix_keeps_the_guarded_value_positional_and_fixes_an_ordinary_function(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--fix inserts the star after the guarded value and still fixes another function in the same file."""
    source_file = tmp_path / "source.py"
    source_file.write_text(_GUARD_WITH_EXTRA + "\n\ndef add(left, right):\n    ...\n")

    monkeypatch.setattr("sys.argv", ["pyrigor", "--fix", "--select=PYR402", str(source_file)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert not exc_info.value.code
    assert source_file.read_text() == _GUARD_FIXED + "\n\ndef add(*, left, right):\n    ...\n"


def test_fix_over_a_directory_fixes_the_guard_file_and_the_other_files(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A directory run fixes a guard file besides its siblings, in a nested folder too."""
    guard_file = tmp_path / "guard.py"
    ordinary_file = tmp_path / "ordinary.py"
    nested_file = tmp_path / "package" / "nested.py"
    nested_file.parent.mkdir()
    guard_file.write_text(_GUARD_WITH_EXTRA)
    ordinary_file.write_text("def add(left, right):\n    ...\n")
    nested_file.write_text("def subtract(left, right):\n    ...\n")
    monkeypatch.setattr("sys.argv", ["pyrigor", "--fix", "--select=PYR402", str(tmp_path)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert not exc_info.value.code
    assert guard_file.read_text() == _GUARD_FIXED
    expected_ordinary = "def add(*, left, right):\n    ...\n"
    expected_nested = "def subtract(*, left, right):\n    ...\n"
    assert ordinary_file.read_text() == expected_ordinary
    assert nested_file.read_text() == expected_nested


def test_suppression_comment_on_a_guard_is_honoured(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A reasoned suppression silences the remaining PYR402 finding on a guard."""
    source_file = tmp_path / "source.py"
    source_file.write_text("def is_int(value, strict) -> TypeGuard[int]:  # pyrigor PYR402 # public API\n    ...\n")
    monkeypatch.setattr("sys.argv", ["pyrigor", "--select=PYR402", str(source_file)])

    with pytest.raises(SystemExit) as exc_info:
        run()

    assert not exc_info.value.code
    assert f"{source_file}:" not in capsys.readouterr().out
