"""Run a scripts/ check as a subprocess against a fixture directory.

Shared by every test module for a scripts/check_*.py script that prints one
problem per line and fails with a non-zero exit code, so each does not
redefine the same locator and subprocess wrapper.
"""

import subprocess  # nosec B404 -- test helper runs a fixed local checker script
import sys
from pathlib import Path
from typing import NamedTuple


class CheckResult(NamedTuple):
    """A check's exit code and the lines it printed."""

    exit_code: int
    lines: list[str]


def find_script(*, name: str) -> Path:
    """Return a scripts/ file, whether run from the repository or a copy under mutants/.

    Args:
        name: The script's filename, for example, 'check_maintainability.py'.

    Returns:
        Its path.

    Raises:
        FileNotFoundError: If no ancestor of this file holds a scripts/ directory containing it.
    """
    for parent in Path(__file__).parents:
        candidate = parent / "scripts" / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"scripts/{name}")


def run_check(*, script: Path, cwd: Path, arguments: list[str]) -> CheckResult:
    """Run a scripts/ check script with the given arguments inside a fixture directory.

    Args:
        script: The check script to run.
        cwd: The fixture directory to run it inside.
        arguments: The command-line arguments to pass it.

    Returns:
        Its exit code and the lines it printed to stdout.
    """
    # ruff PLW1510 and pylint W1510 require an explicit check argument.
    # noinspection PyArgumentEqualDefault
    result = subprocess.run(  # nosec B603 # noqa: S603 -- a scripts/ check script with fixed test arguments
        [sys.executable, str(script), *arguments],
        cwd=cwd,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    return CheckResult(exit_code=result.returncode, lines=result.stdout.splitlines())


def write_fixture(*, directory: Path, name: str, content: str) -> None:
    """Write one fixture module, creating its parent directories.

    Args:
        directory: The fixture directory to write into.
        name: The module's filename, relative to the directory.
        content: The module's source.
    """
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
