"""Auto-sync tooling when pyproject.toml's version changes.

Runs `pre-commit auto update` and `uv lock` when a version bump is
detected in the staged diff, keeping pinned hook versions (including
pyrigor's own self-hosted entry) and the lockfile from drifting.
Real limitation: at release-commit time, the new tag does not exist
yet, so this only catches up on the commit *after* a release, not
the release commit itself.
"""

import subprocess  # nosec -- fixed, local tooling commands only
import sys


# noinspection LongLine
def _staged_files() -> list[str]:
    """Get the list of staged file paths.

    Returns:
        Every file is staged for this commit.
    """
    # noinspection PyArgumentEqualDefault, PyPep8
    result = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, check=False)  # nosec # pylint: disable=line-too-long
    return result.stdout.splitlines()


# noinspection LongLine
def _pyproject_version_changed() -> bool:
    """Check whether pyproject.toml's version line changed in the staged diff.

    Returns:
        True if a version bump is present in the staged diff.
    """
    # noinspection PyArgumentEqualDefault, PyPep8
    result = subprocess.run(
        ["git", "diff", "--cached", "--", "pyproject.toml"], capture_output=True, text=True, check=False
    )  # nosec # pylint: disable=line-too-long
    return any(line.startswith("+version") for line in result.stdout.splitlines())


def main() -> None:
    """Run pre-commit auto update and uv lock if a version bump is staged, then prompt to re-commit."""
    if "pyproject.toml" not in _staged_files() or not _pyproject_version_changed():
        sys.exit(0)

    print("pyproject.toml version changed: running pre-commit autoupdate and uv lock.")
    subprocess.run(["pre-commit", "autoupdate"], check=True)  # nosec
    subprocess.run(["uv", "lock"], check=True)  # nosec

    # noinspection PyArgumentEqualDefault
    result = subprocess.run(  # nosec
        ["git", "diff", "--name-only", "--", ".pre-commit-config.yaml", "uv.lock"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.stdout.strip():
        print("Done. Re-stage any changed files (.pre-commit-config.yaml, uv.lock) and commit again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
