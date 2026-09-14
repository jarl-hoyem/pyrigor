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

from dev_tooling_shared import PRE_COMMIT_CONFIG, PYPROJECT_TOML, pyproject_version_changed, staged_files


def main() -> None:
    """Run pre-commit auto update and uv lock if a version bump is staged, then prompt to re-commit."""
    if PYPROJECT_TOML not in staged_files(check=True) or not pyproject_version_changed(check=True):
        sys.exit(0)

    print(f"{PYPROJECT_TOML} version changed: running pre-commit autoupdate and uv lock.")
    subprocess.run(["pre-commit", "autoupdate"], check=True)  # nosec # noqa: S607
    subprocess.run(["uv", "lock"], check=True)  # nosec # noqa: S607

    # noinspection PyArgumentEqualDefault
    result = subprocess.run(  # nosec  # noqa: S603 -- arguments are fixed module constants, no untrusted input
        ["git", "diff", "--name-only", "--", PRE_COMMIT_CONFIG, "uv.lock"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.stdout.strip():
        print(f"Done. Re-stage any changed files ({PRE_COMMIT_CONFIG}, uv.lock) and commit again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
