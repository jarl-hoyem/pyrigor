"""Warn-only Definition of Done checks, run as a pre-commit hook.

Never fails the commit. Prints a note pointing at
guidelines/DEFINITION_OF_DONE.md when a diff pattern suggests a
step might have been missed.
"""

import subprocess  # nosec -- fixed git commands only, no untrusted input
import sys

_PYPROJECT_TOML = "pyproject.toml"
_CHANGELOG_MD = "CHANGELOG.md"
_RULES_PY = "pyrigor/rules.py"
_README_MD = "README.md"


def _staged_files() -> list[str]:
    """Get the list of staged file paths.

    Returns:
        Every file that is staged for this commit.
    """
    # A fixed argument list, no untrusted input reaches the subprocess here.
    result = subprocess.run(  # nosec
        ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, check=True
    )
    return result.stdout.splitlines()


def _pyproject_version_changed() -> bool:
    """Check whether pyproject.toml's version line changed in the staged diff.

    Returns:
        True if a version bump is present in the staged diff.
    """
    # A fixed argument list, no untrusted input reaches the subprocess here.
    result = subprocess.run(  # nosec
        ["git", "diff", "--cached", "--", "pyproject.toml"], capture_output=True, text=True, check=True
    )
    return any(line.startswith("+version") for line in result.stdout.splitlines())


def _check_changelog_sync(*, files: list[str]) -> None:
    """Warn if pyproject.toml's version changed without a CHANGELOG.md entry.

    Args:
        files: Every staged path.
    """
    if _PYPROJECT_TOML in files and _pyproject_version_changed() and _CHANGELOG_MD not in files:
        print("Note: pyproject.toml version changed but CHANGELOG.md did not. See guidelines/DEFINITION_OF_DONE.md.")


def _check_readme_sync(*, files: list[str]) -> None:
    """Warn if a checker or rules.py changed without a README.md update.

    Args:
        files: Every staged path.
    """
    checker_files_changed = any(f.startswith("pyrigor/checkers/") or f == _RULES_PY for f in files)
    if checker_files_changed and _README_MD not in files:
        print(
            "Note: pyrigor/checkers or rules.py changed but README.md did not. "
            "Confirm this is intentional. See guidelines/DEFINITION_OF_DONE.md."
        )


def main() -> None:
    """Run both warn-only checks."""
    files = _staged_files()
    _check_changelog_sync(files=files)
    _check_readme_sync(files=files)
    sys.exit(0)


if __name__ == "__main__":
    main()
