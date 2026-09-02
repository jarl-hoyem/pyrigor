"""Enforce a minimum mutation score from mutmut's exported CI/CD stats.

Reads the JSON that `mutmut export-cicd-stats` writes and fails when the
mutation score falls below the required floor.

Timeouts are left out of the score. They track machine load rather than test
quality, so counting them would make the gate flaky. Every other unkilled
mutant counts against the score.
"""

import json
import sys
from pathlib import Path
from typing import Final, NamedTuple, cast

STATS_PATH: Final = Path("mutants") / "mutmut-cicd-stats.json"
MINIMUM_SCORE: Final = 80.0

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
        The stats mapping.

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
    return cast("dict[str, object]", loaded)


def _count(*, stats: dict[str, object], key: str, path: Path) -> int:
    """Read one integer count out of the stats mapping.

    Args:
        stats: The stats mapping.
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
        stats: The stats mapping.
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
    """Report the mutation score and enforce the floor.

    Returns:
        0 when the score meets the floor, 1 when it does not.
    """
    score = _mutation_score(stats=_load_stats(path=STATS_PATH), path=STATS_PATH)
    print(
        f"mutation score {score.percentage:.2f}% "
        f"({score.killed}/{score.scored} killed, {score.survived} survived, "
        f"{score.timeout} timeout excluded)",
    )

    if score.percentage < MINIMUM_SCORE:
        print(f"mutation score is below the required {MINIMUM_SCORE}%", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
