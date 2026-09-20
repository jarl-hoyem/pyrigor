"""Enforce a maximum survivor count from mutmut's exported CI/CD stats.

Reads the JSON that `mutmut export-cicd-stats` writes and fails when the
surviving mutants exceed the required cap.

Timeouts are left out of the score. They track the machine load rather than test
quality, so counting them would make the gate flaky. Every other unkilled
mutant counts against the cap.
"""

import json
import sys
from pathlib import Path
from typing import Final, NamedTuple, cast

STATS_PATH: Final = Path("mutants") / "mutmut-cicd-stats.json"

# Set from a real, clean mutmut run, never assumed. Raise it only from another
# real measurement, and only when the survivor total itself moved (killing more
# mutants, or mutmut's own mutant generation changing the total).
MAX_SURVIVING_MUTANTS: Final = 31

# Slack below the cap, so two contributors killing mutants in parallel do not
# collide: each kill lowers the real count without needing the cap lowered in
# the same commit. See the "lower it to N" report in main() below.
SURVIVOR_CAP_HEADROOM: Final = 5

_PERCENT: Final = 100.0
_COUNT_KEYS: Final = ("total", "killed", "survived", "timeout")


class MutationScore(NamedTuple):
    """A mutation score and the counts behind it."""

    percentage: float
    killed: int
    scored: int
    survived: int
    timeout: int


def _load_stats(*, path: Path) -> dict[str, object]:
    """Load mutmut's exported stats.

    Args:
        path: The exported stats file.

    Returns:
        The statistics mapping.

    Raises:
        SystemExit: If the file cannot be read or does not hold a JSON object.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        message = f"{path}: cannot read mutmut stats ({error}). Did 'mutmut export-cicd-stats' run?"
        raise SystemExit(message) from error

    try:
        loaded: object = json.loads(raw)
    except json.JSONDecodeError as error:
        raise SystemExit(f"{path}: not valid JSON ({error})") from error

    if not isinstance(loaded, dict):
        raise SystemExit(f"{path}: expected a JSON object, found {type(loaded).__name__}")

    # A JSON object's keys are strings by definition, so the cast holds after the isinstance check.
    # Pyright reports the return type as partially unknown without it. PyCharm has no unknown type.
    # noinspection PyUnnecessaryCast
    return cast("dict[str, object]", loaded)


def _count(*, stats: dict[str, object], key: str, path: Path) -> int:
    """Read one integer count out of the statistics mapping.

    Args:
        stats: The statistics mapping.
        key: The count to read.
        path: The file the stats came from, for error messages.

    Returns:
        The count.

    Raises:
        SystemExit: If the key is missing or is not an integer.
    """
    value = stats.get(key)
    if not isinstance(value, int):
        raise SystemExit(f"{path}: missing or non-integer '{key}'")
    return value


def _mutation_score(*, stats: dict[str, object], path: Path) -> MutationScore:
    """Derive the mutation score, excluding timeouts from the denominator.

    Args:
        stats: The statistics mapping.
        path: The file the stats came from, for error messages.

    Returns:
        The score and the counts behind it.

    Raises:
        SystemExit: If the run produced nothing that could be scored.
    """
    counts = {key: _count(stats=stats, key=key, path=path) for key in _COUNT_KEYS}
    scored = counts["total"] - counts["timeout"]
    if counts["total"] <= 0:
        raise SystemExit(f"{path}: no mutants were generated, so nothing was measured")
    if scored <= 0:
        raise SystemExit(f"{path}: every mutant timed out, so nothing could be scored")

    return MutationScore(
        percentage=counts["killed"] / scored * _PERCENT,
        killed=counts["killed"],
        scored=scored,
        survived=counts["survived"],
        timeout=counts["timeout"],
    )


def main() -> int:
    """Report the mutation score and enforce the survivor cap.

    Returns:
        0 when survivors are at or below the cap, 1 when they exceed it.
    """
    score = _mutation_score(stats=_load_stats(path=STATS_PATH), path=STATS_PATH)
    print(
        f"mutation score {score.percentage:.2f}% "
        f"({score.killed}/{score.scored} killed, {score.survived} survived, "
        f"{score.timeout} timeout excluded)",
    )

    if score.survived > MAX_SURVIVING_MUTANTS:
        print(
            f"mutation survivors {score.survived} exceed the required maximum {MAX_SURVIVING_MUTANTS}",
            file=sys.stderr,
        )
        return 1
    if score.survived <= MAX_SURVIVING_MUTANTS - SURVIVOR_CAP_HEADROOM:
        print(f"mutation survivor cap is loose; lower it to {score.survived}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
