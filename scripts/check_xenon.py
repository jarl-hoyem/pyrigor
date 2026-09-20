"""Fail when a Python file's cyclomatic complexity exceeds its grade.

The tool xenon has no per-function suppression, unlike complexipy's inline
'# complexipy: ignore'. A file with a real, documented exception is named
once with --relax, checked at grade B instead of the strict default A. The
strict set is derived as every other file, not separately maintained, so it
cannot drift out of agreement with --relax (#309).
"""

import argparse
import subprocess  # nosec B404 -- runs xenon on the hook's own file list
from pathlib import Path
from typing import Final, NamedTuple

from dev_tooling_shared import find_executable

_STRICT: Final = "A"
_RELAXED: Final = "B"


class _Partition(NamedTuple):
    """A checked file list split into the strict set and the relaxed files present among them."""

    strict: list[str]
    present_relaxed: list[str]


def _run_xenon(*, xenon: str, absolute: str, files: list[str]) -> bool:
    """Run xenon on a file list at one grade, letting its own report reach the console.

    Args:
        xenon: Absolute path of the xenon executable.
        absolute: The --max-absolute grade to enforce; modules and average stay strict.
        files: The files to check.

    Returns:
        True when xenon passed, or there was nothing to check.
    """
    if not files:
        return True
    # noinspection PyArgumentEqualDefault
    result = subprocess.run(  # nosec B603 # noqa: S603 -- xenon with a fixed grade and the hook's own file list
        [xenon, f"--max-absolute={absolute}", f"--max-modules={_STRICT}", f"--max-average={_STRICT}", *files],
        check=False,
    )
    return not result.returncode


def _stale_relaxation(*, xenon: str, path: str) -> str | None:
    """Return a problem when a relaxed file already passes the strict grade on its own.

    Args:
        xenon: Absolute path of the xenon executable.
        path: The relaxed file to check.

    Returns:
        A message naming the file when it no longer needs relaxing. None otherwise.
    """
    # noinspection PyArgumentEqualDefault
    result = subprocess.run(  # nosec B603 # noqa: S603 -- xenon at strict grade against one relaxed file
        [xenon, f"--max-absolute={_STRICT}", f"--max-modules={_STRICT}", f"--max-average={_STRICT}", path],
        capture_output=True,
        check=False,
    )
    if not result.returncode:
        return f"{path}: ranks {_STRICT} now, remove its --relax entry"
    return None


def _partition(*, relaxed: list[str], files: list[str]) -> _Partition:
    """Split the checked files into the strict set and the relaxed files present among them.

    Args:
        relaxed: The POSIX paths --relax names.
        files: The POSIX paths that were checked.

    Returns:
        Every checked file not named by --relax, and the relaxed files that were actually checked.
    """
    return _Partition(
        strict=[path for path in files if path not in relaxed],
        present_relaxed=[path for path in relaxed if path in files],
    )


def _relax_problems(*, xenon: str, relaxed: list[str], files: list[str], present_relaxed: list[str]) -> list[str]:
    """Return one problem per --relax entry that is missing or no longer needed.

    Args:
        xenon: Absolute path of the xenon executable.
        relaxed: The POSIX paths --relax names.
        files: The POSIX paths that were checked.
        present_relaxed: The relaxed files that were actually checked.

    Returns:
        A message per entry naming a file that was not checked, and per file that no longer needs relaxing.
    """
    problems = [f"{path}: --relax names a file that was not checked" for path in relaxed if path not in files]
    problems.extend(problem for path in present_relaxed if (problem := _stale_relaxation(xenon=xenon, path=path)))
    return problems


def _passed(*, problems: list[str], strict_passed: bool, relaxed_passed: bool) -> bool:
    """Return whether every part of the check passed.

    Args:
        problems: The '--relax' entries that were missing or no longer needed.
        strict_passed: Whether the strict-grade pass succeeded.
        relaxed_passed: Whether the relaxed-grade pass succeeded.

    Returns:
        True only when there were no problems and both passes succeeded.
    """
    return not problems and strict_passed and relaxed_passed


def main() -> int:
    """Check the files given as arguments, printing each problem and failing when there is one."""
    parser = argparse.ArgumentParser(description="Fail when a file's cyclomatic complexity exceeds its grade.")
    parser.add_argument("--relax", action="append", default=[], help="A file relaxed to grade B, repeatable.")
    parser.add_argument("files", nargs="*")
    arguments = parser.parse_args()

    relaxed = [Path(path).as_posix() for path in arguments.relax]
    files = [Path(path).as_posix() for path in arguments.files]
    partition = _partition(relaxed=relaxed, files=files)

    xenon = find_executable(name="xenon")
    problems = _relax_problems(xenon=xenon, relaxed=relaxed, files=files, present_relaxed=partition.present_relaxed)
    strict_passed = _run_xenon(xenon=xenon, absolute=_STRICT, files=partition.strict)
    relaxed_passed = _run_xenon(xenon=xenon, absolute=_RELAXED, files=partition.present_relaxed)

    for problem in problems:
        print(problem)
    return 0 if _passed(problems=problems, strict_passed=strict_passed, relaxed_passed=relaxed_passed) else 1


if __name__ == "__main__":
    raise SystemExit(main())
