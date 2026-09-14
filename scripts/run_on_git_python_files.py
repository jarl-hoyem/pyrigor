"""Run a whole-project tool on every Python file that git does not ignore.

Git decides what is generated or vendored, through .gitignore. Tools that
cannot read .gitignore receive this file list instead of scanning the working
tree, so no tool needs an exclusion list of its own.
"""

import shutil
import subprocess  # nosec B404 -- runs git and the tool named by the hook's own entry
import sys
from pathlib import Path


def python_files(*, git: str) -> list[str]:
    """Return the tracked and untracked Python files that git does not ignore.

    Args:
        git: Absolute path of the git executable.

    Returns:
        Repository-relative paths that still exist on disk.
    """
    result = subprocess.run(  # nosec B603  # noqa: S603 -- fixed git arguments, executable resolved by shutil.which
        [git, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--deduplicate", "--", "*.py"],
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    return [path for path in result.stdout.split("\0") if path and Path(path).is_file()]


def _find_executable(*, name: str) -> str:
    """Return the absolute path of an executable on PATH, exiting with 127 when it is missing.

    Args:
        name: The executable to look up.

    Returns:
        Its absolute path.
    """
    path = shutil.which(name)
    if path is None:
        print(f"command not found: {name}", file=sys.stderr)
        raise SystemExit(127)
    return path


def main() -> int:
    """Run the given command with the Python file list appended, returning its exit code."""
    command = sys.argv[1:]
    if not command:
        print("usage: run_on_git_python_files.py TOOL [ARGS...]", file=sys.stderr)
        return 2
    git = _find_executable(name="git")
    tool = _find_executable(name=command[0])
    files = python_files(git=git)
    if not files:
        print("No Python files to check.")
        return 0
    # ruff PLW1510 and pylint W1510 require an explicit check argument.
    # noinspection PyArgumentEqualDefault
    result = subprocess.run(  # nosec B603 # noqa: S603 -- command comes from the hook entry
        [tool, *command[1:], *files],
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
