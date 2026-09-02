"""Tests for scripts/check_mutation_score.py's mutation-score gate.

Runs the script itself as a subprocess against a throwaway stats file, rather
than importing its internals. The scripts/ directory is not a package, and this
matches REVIEW_CHECKLIST.md's preference for testing the real invocation.
"""
# pylint: disable=duplicate-code  # Independent subprocess setup is deliberate in this test module.
# test assertions compare against expected literal values by design,
# not a magic-value problem
# pylint: disable=magic-value-comparison

import importlib.util
import json
import subprocess  # nosec B404 -- test invokes a fixed local checker script
import sys
from math import ceil
from pathlib import Path
from typing import Final

_SCRIPT_NAME = "check_mutation_score.py"
_STATS_NAME = "mutmut-cicd-stats.json"

# Named, so the assertions read as exit codes rather than as truthiness checks.
_EXIT_SUCCESS = 0
_EXIT_FAILURE = 1


def _script_path() -> Path:
    """Locate the checker script, including when tests run from mutmut's mutants/ copy.

    Returns:
        The path to the checker script.
    """
    candidate = Path(__file__).parents[1] / "scripts" / _SCRIPT_NAME
    if candidate.exists():
        return candidate

    for parent in Path(__file__).parents[1].parents:
        found = parent / "scripts" / _SCRIPT_NAME
        if found.exists():
            return found
    return candidate


def _floor() -> float:
    """Read the checker's own MINIMUM_SCORE rather than repeating its value.

    Every fixture below is derived from this. Moving the floor therefore moves
    the fixtures with it, instead of silently turning boundary cases into
    meaningless ones.

    Returns:
        The checker's minimum score.

    Raises:
        RuntimeError: If the checker cannot be loaded as a module.
    """
    spec = importlib.util.spec_from_file_location("check_mutation_score", _script_path())
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {_script_path()}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return float(module.MINIMUM_SCORE)


_TOTAL: Final = 1000
_FLOOR: Final = _floor()

# The smallest killed count that still meets the floor, so _AT_FLOOR - 1 fails.
_AT_FLOOR: Final = ceil(_FLOOR / 100 * _TOTAL)


def _run(*, tmp_path: Path, raw: str | None) -> subprocess.CompletedProcess[str]:
    """Run the checker against a temporary stats file.

    Args:
        tmp_path: The working directory to run inside.
        raw: The stats file's contents, or None to leave the file absent.

    Returns:
        The completed process, with captured output.
    """
    mutants = tmp_path / "mutants"
    mutants.mkdir()
    if raw is not None:
        (mutants / _STATS_NAME).write_text(raw, encoding="utf-8")

    # noinspection PyArgumentEqualDefault
    return subprocess.run(  # nosec B603 -- fixed script path, throwaway directory # noqa: S603
        [sys.executable, str(_script_path())],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


def _stats(*, total: int, killed: int, survived: int, timeout: int) -> str:
    """Build a stats file body.

    Args:
        total: Every mutant generated.
        killed: Mutants the tests caught.
        survived: Mutants the tests missed.
        timeout: Mutants that ran out of time.

    Returns:
        The JSON body.
    """
    return json.dumps({"total": total, "killed": killed, "survived": survived, "timeout": timeout})


def test_score_above_floor_passes(*, tmp_path: Path) -> None:
    """A score comfortably above the floor should exit zero."""
    killed = _AT_FLOOR + 50
    body = _stats(total=_TOTAL, killed=killed, survived=_TOTAL - killed, timeout=0)

    result = _run(tmp_path=tmp_path, raw=body)

    assert result.returncode == _EXIT_SUCCESS
    assert f"{killed / _TOTAL * 100:.2f}%" in result.stdout


def test_score_below_floor_fails(*, tmp_path: Path) -> None:
    """A score under the floor should exit non-zero and say so."""
    killed = _AT_FLOOR - 50
    body = _stats(total=_TOTAL, killed=killed, survived=_TOTAL - killed, timeout=0)

    result = _run(tmp_path=tmp_path, raw=body)

    assert result.returncode == _EXIT_FAILURE
    assert f"{killed / _TOTAL * 100:.2f}%" in result.stdout
    assert "below the required" in result.stderr


def test_score_exactly_at_floor_passes(*, tmp_path: Path) -> None:
    """The floor is inclusive, so a score exactly on it should pass.

    Guards the boundary against a fix that flips the comparison to '<='.
    """
    body = _stats(total=_TOTAL, killed=_AT_FLOOR, survived=_TOTAL - _AT_FLOOR, timeout=0)

    result = _run(tmp_path=tmp_path, raw=body)

    assert result.returncode == _EXIT_SUCCESS


def test_score_one_killed_mutant_below_the_floor_fails(*, tmp_path: Path) -> None:
    """One killed mutant fewer than the floor demands should fail.

    This is the tightest boundary available. Together with the test above it
    pins the comparison exactly at the floor, at whatever value the floor holds.
    """
    killed = _AT_FLOOR - 1
    body = _stats(total=_TOTAL, killed=killed, survived=_TOTAL - killed, timeout=0)

    result = _run(tmp_path=tmp_path, raw=body)

    assert result.returncode == _EXIT_FAILURE


def test_timeouts_are_excluded_from_the_score(*, tmp_path: Path) -> None:
    """Timeouts leave the denominator, so they cannot drag the score under the floor.

    Every scored mutant is killed here, so excluding timeouts gives 100%.
    Counting them instead puts the score just under the floor. Deriving both
    counts from the floor keeps this discriminating at any floor value.
    """
    scored = _AT_FLOOR - 1
    timeout = _TOTAL - scored
    body = _stats(total=_TOTAL, killed=scored, survived=0, timeout=timeout)

    result = _run(tmp_path=tmp_path, raw=body)

    assert result.returncode == _EXIT_SUCCESS
    assert f"{timeout} timeout excluded" in result.stdout


def test_missing_stats_file_is_an_error(*, tmp_path: Path) -> None:
    """An absent stats file should fail loudly, not be read as a passing score."""
    result = _run(tmp_path=tmp_path, raw=None)

    assert result.returncode != _EXIT_SUCCESS
    assert "cannot read mutmut stats" in result.stderr


def test_no_mutants_generated_is_an_error(*, tmp_path: Path) -> None:
    """A run that produced no mutants measured nothing, so it must not pass."""
    body = _stats(total=0, killed=0, survived=0, timeout=0)

    result = _run(tmp_path=tmp_path, raw=body)

    assert result.returncode != _EXIT_SUCCESS
    assert "no mutants were generated" in result.stderr


def test_every_mutant_timing_out_is_an_error(*, tmp_path: Path) -> None:
    """If timeouts consume the whole run there is nothing left to score."""
    body = _stats(total=5, killed=0, survived=0, timeout=5)

    result = _run(tmp_path=tmp_path, raw=body)

    assert result.returncode != _EXIT_SUCCESS
    assert "nothing could be scored" in result.stderr


def test_malformed_json_is_an_error(*, tmp_path: Path) -> None:
    """A truncated or corrupt stats file should fail loudly."""
    result = _run(tmp_path=tmp_path, raw='{"total": 10,')

    assert result.returncode != _EXIT_SUCCESS
    assert "not valid JSON" in result.stderr


def test_json_that_is_not_an_object_is_an_error(*, tmp_path: Path) -> None:
    """Valid JSON of the wrong shape should fail loudly."""
    result = _run(tmp_path=tmp_path, raw="[1, 2, 3]")

    assert result.returncode != _EXIT_SUCCESS
    assert "expected a JSON object" in result.stderr


def test_missing_count_key_is_an_error(*, tmp_path: Path) -> None:
    """A stats file missing a count mutmut normally writes should fail loudly."""
    result = _run(tmp_path=tmp_path, raw=json.dumps({"total": 10, "killed": 10, "survived": 0}))

    assert result.returncode != _EXIT_SUCCESS
    assert "'timeout'" in result.stderr


def test_non_integer_count_is_an_error(*, tmp_path: Path) -> None:
    """A count that is not an integer should fail loudly rather than be coerced."""
    body = json.dumps({"total": 10, "killed": "10", "survived": 0, "timeout": 0})

    result = _run(tmp_path=tmp_path, raw=body)

    assert result.returncode != _EXIT_SUCCESS
    assert "'killed'" in result.stderr
