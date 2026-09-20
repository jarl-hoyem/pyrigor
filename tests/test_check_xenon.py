"""Tests for the check that gates xenon's cyclomatic-complexity grade on one --relax list.

Each test writes fixture modules into a temporary directory and runs the check
as a subprocess against the real xenon binary, the way the pre-commit hook
does. Files are passed as explicit arguments, the same way
scripts/run_on_git_python_files.py appends them for the real hook.
"""

from pathlib import Path

from tests.script_checks import find_script, run_check, write_fixture

_FAILURE = 1
_SCRIPT = find_script(name="check_xenon.py")


def _branchy_module(*, branches: int) -> str:
    """Return a module whose one-target function's complexity grows with branches.

    Four trivial companion functions keep the module's average and per-module
    rank at grade A even when the target function itself ranks higher, the
    same shape as the real _shared.py file this check exists for.
    """
    lines = ["def branchy(x):", "    total = 0"]
    for index in range(branches):
        lines.append(f"    if x == {index}:")
        lines.append(f"        total += {index}")
    lines.append("    return total")
    companions = "\n".join(f"def trivial_{index}(x):\n    return x + {index}" for index in range(4))
    return "\n".join(lines) + "\n\n\n" + companions + "\n"


_GRADE_A = _branchy_module(branches=2)
_GRADE_B = _branchy_module(branches=8)
_GRADE_C = _branchy_module(branches=15)


def test_all_files_at_grade_a_pass(*, tmp_path: Path) -> None:
    """No relaxed files and everything at grade A passes."""
    write_fixture(directory=tmp_path, name="simple.py", content=_GRADE_A)

    result = run_check(script=_SCRIPT, cwd=tmp_path, arguments=["simple.py"])

    assert not result.exit_code
    assert not result.lines


def test_unrelaxed_file_below_grade_a_fails(*, tmp_path: Path) -> None:
    """A file at grade B with no --relax entry fails the strict pass."""
    write_fixture(directory=tmp_path, name="branchy.py", content=_GRADE_B)

    result = run_check(script=_SCRIPT, cwd=tmp_path, arguments=["branchy.py"])

    assert result.exit_code == _FAILURE


def test_relaxed_file_at_grade_b_passes(*, tmp_path: Path) -> None:
    """A file relaxed to grade B that genuinely needs it passes."""
    write_fixture(directory=tmp_path, name="branchy.py", content=_GRADE_B)

    result = run_check(script=_SCRIPT, cwd=tmp_path, arguments=["--relax=branchy.py", "branchy.py"])

    assert not result.exit_code
    assert not result.lines


def test_relaxed_file_still_below_grade_b_fails(*, tmp_path: Path) -> None:
    """A file relaxed to B that ranks C still fails; relaxation is not a blanket pass."""
    write_fixture(directory=tmp_path, name="branchy.py", content=_GRADE_C)

    result = run_check(script=_SCRIPT, cwd=tmp_path, arguments=["--relax=branchy.py", "branchy.py"])

    assert result.exit_code == _FAILURE


def test_relaxed_file_at_grade_a_reports_stale_entry(*, tmp_path: Path) -> None:
    """A relaxed entry for a file that already ranks A on its own is reported and fails."""
    write_fixture(directory=tmp_path, name="simple.py", content=_GRADE_A)

    result = run_check(script=_SCRIPT, cwd=tmp_path, arguments=["--relax=simple.py", "simple.py"])

    assert result.exit_code == _FAILURE
    assert result.lines == ["simple.py: ranks A now, remove its --relax entry"]


def test_relax_entry_for_an_unchecked_file_fails(*, tmp_path: Path) -> None:
    """A --relax entry naming a file that was not in the checked list fails, not silently."""
    write_fixture(directory=tmp_path, name="simple.py", content=_GRADE_A)

    result = run_check(script=_SCRIPT, cwd=tmp_path, arguments=["--relax=missing.py", "simple.py"])

    assert result.exit_code == _FAILURE
    assert result.lines == ["missing.py: --relax names a file that was not checked"]


def test_strict_and_relaxed_files_are_judged_independently(*, tmp_path: Path) -> None:
    """An unrelaxed grade A file and a relaxed grade B file both pass together."""
    write_fixture(directory=tmp_path, name="simple.py", content=_GRADE_A)
    write_fixture(directory=tmp_path, name="branchy.py", content=_GRADE_B)

    result = run_check(script=_SCRIPT, cwd=tmp_path, arguments=["--relax=branchy.py", "simple.py", "branchy.py"])

    assert not result.exit_code
    assert not result.lines


def test_no_files_passes(*, tmp_path: Path) -> None:
    """With no files given, there is nothing to check."""
    result = run_check(script=_SCRIPT, cwd=tmp_path, arguments=[])

    assert not result.exit_code
    assert not result.lines
