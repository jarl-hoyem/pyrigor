"""Tests for scripts/check_mutation_score.py's mutation-score gate.

Runs the script itself as a subprocess against a throwaway stats file, rather
than importing its internals. The scripts/ directory is not a package, and this
matches REVIEW_CHECKLIST.md's preference for testing the real invocation.
"""
# pylint: disable=duplicate-code  # Independent subprocess setup is deliberate in this test module.
# test assertions compare against expected literal values by design,
# not a magic-value problem
# pylint: disable=magic-value-comparison

import json
import subprocess  # nosec B404 -- test invokes a fixed local checker script
import sys
from pathlib import Path

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
    body = _stats(total=1000, killed=995, survived=5, timeout=0)

    result = _run(tmp_path=tmp_path, raw=body)

    assert result.returncode == _EXIT_SUCCESS
    assert "99.50%" in result.stdout


def test_score_below_floor_fails(*, tmp_path: Path) -> None:
    """A score under the floor should exit non-zero and say so."""
    body = _stats(total=1000, killed=985, survived=15, timeout=0)

    result = _run(tmp_path=tmp_path, raw=body)

    assert result.returncode == _EXIT_FAILURE
    assert "98.50%" in result.stdout
    assert "below the required" in result.stderr


def test_score_exactly_at_floor_passes(*, tmp_path: Path) -> None:
    """The floor is inclusive, so a score exactly on it should pass.

    Guards the boundary against a fix that flips the comparison to '<='.
    """
    body = _stats(total=1000, killed=990, survived=10, timeout=0)

    result = _run(tmp_path=tmp_path, raw=body)

    assert result.returncode == _EXIT_SUCCESS
    assert "99.00%" in result.stdout


def test_timeouts_are_excluded_from_the_score(*, tmp_path: Path) -> None:
    """Timeouts leave the denominator, so they cannot drag the score under the floor.

    Counting the fifteen timeouts as failures would give 98.50% and fail.
    Excluding them scores 985 of 985, which passes.
    """
    body = _stats(total=1000, killed=985, survived=0, timeout=15)

    result = _run(tmp_path=tmp_path, raw=body)

    assert result.returncode == _EXIT_SUCCESS
    assert "15 timeout excluded" in result.stdout


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
