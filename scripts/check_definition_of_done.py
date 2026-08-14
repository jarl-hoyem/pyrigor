"""Warn-only Definition of Done checks, run as a pre-commit hook.

Never fails the commit. Prints a note pointing at
guidelines/DEFINITION_OF_DONE.md when a diff pattern suggests a
step might have been missed.
"""

import subprocess
import sys


def _staged_files() -> list[str]:
    """Get the list of staged file paths.

    Returns:
        Every file that is staged for this commit.
    """
    result = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, check=True)
    return result.stdout.splitlines()


def _pyproject_version_changed() -> bool:
    """Check whether pyproject.toml's version line changed in the staged diff.

    Returns:
        True if a version bump is present in the staged diff.
    """
    result = subprocess.run(["git", "diff", "--cached", "pyproject.toml"], capture_output=True, text=True, check=True)
    return any(line.startswith("+version") for line in result.stdout.splitlines())


def main() -> None:
    """Run both warn-only checks."""
    files = _staged_files()

    if "pyproject.toml" in files and _pyproject_version_changed() and "CHANGELOG.md" not in files:
        print("Note: pyproject.toml version changed but CHANGELOG.md did not. See guidelines/DEFINITION_OF_DONE.md.")

    checker_files_changed = any(f.startswith("pyrigor/checkers/") or f == "pyrigor/rules.py" for f in files)
    if checker_files_changed and "README.md" not in files:
        print(
            "Note: pyrigor/checkers or rules.py changed but README.md did not. "
            "Confirm this is intentional. See guidelines/DEFINITION_OF_DONE.md."
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
