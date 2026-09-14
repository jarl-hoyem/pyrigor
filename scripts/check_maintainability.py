"""Fail when a Python file's maintainability index ranks below A.

The radon tool reports the maintainability index but never fails on it, so this
check turns its ranks into an exit code. A module still waiting to be split can
be listed with --allow. An entry fails once its module no longer needs it.
"""

import argparse
import json
import subprocess  # nosec B404 -- runs radon on the file list the hook passes
from pathlib import Path

from dev_tooling_shared import find_executable

_PASSING_RANK = "A"
_ERROR_KEY = "error"


def radon_report(*, radon: str, files: list[str]) -> dict[str, dict[str, object]]:
    """Return radon's maintainability report, keyed by each file's POSIX path.

    Args:
        radon: Absolute path of the radon executable.
        files: The Python files to analyse.

    Returns:
        One entry per file, holding its maintainability index and rank, or an error message.
    """
    result = subprocess.run(  # nosec B603 # noqa: S603 -- radon with the hook's own file list
        [radon, "mi", "--json", *files],
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    report: dict[str, dict[str, object]] = json.loads(result.stdout)
    return {Path(path).as_posix(): entry for path, entry in report.items()}


def _rank_problem(*, path: str, mi: object, rank: object, allowed: bool) -> str | None:
    """Return the problem with one analysed file's rank when there is one.

    Args:
        path: The file's POSIX path.
        mi: Its maintainability index.
        rank: Its rank, from A to C.
        allowed: Whether the --allow option names the file.

    Returns:
        A message when the file ranks below A without an entry, or ranks A with one. None when neither applies.
    """
    if rank == _PASSING_RANK:
        return f"{path}: ranks {_PASSING_RANK} now, remove its --allow entry" if allowed else None
    return None if allowed else f"{path}: maintainability index {mi} ranks {rank}, below {_PASSING_RANK}"


def _stale_entries(*, report: dict[str, dict[str, object]], allowed: list[str]) -> list[str]:
    """Return one message per --allow entry that names a file outside the report.

    Args:
        report: Radon's report, keyed by each file's POSIX path.
        allowed: The POSIX paths that the '--allow' option names.

    Returns:
        A message per entry for a file that is not checked, for example, after a rename.
    """
    return [f"{path}: --allow names a file that is not checked" for path in allowed if path not in report]


def find_problems(*, report: dict[str, dict[str, object]], allowed: list[str]) -> list[str]:
    """Return every problem in the report, in path order.

    Args:
        report: Radon's report, keyed by each file's POSIX path.
        allowed: The POSIX paths that the '--allow' option names.

    Returns:
        A message per failing file and per unneeded entry. The list is empty when everything passes.
    """
    problems = _stale_entries(report=report, allowed=allowed)
    for path, entry in sorted(report.items()):
        if _ERROR_KEY in entry:
            problems.append(f"{path}: radon could not analyse it: {entry[_ERROR_KEY]}")
            continue
        problem = _rank_problem(path=path, mi=entry["mi"], rank=entry["rank"], allowed=path in allowed)
        if problem is not None:
            problems.append(problem)
    return problems


def main() -> int:
    """Check the files given as arguments, printing each problem and failing when there is one."""
    parser = argparse.ArgumentParser(description="Fail when a file's maintainability index ranks below A.")
    parser.add_argument("--allow", action="append", default=[], help="A file allowed below rank A, repeatable.")
    parser.add_argument("files", nargs="*")
    arguments = parser.parse_args()
    allowed = [Path(path).as_posix() for path in arguments.allow]
    report = radon_report(radon=find_executable(name="radon"), files=arguments.files) if arguments.files else {}
    problems = find_problems(report=report, allowed=allowed)
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
