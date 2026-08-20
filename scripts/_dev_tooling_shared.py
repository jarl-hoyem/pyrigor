"""Shared helpers for pyrigor's own dev-tooling scripts (staged-file inspection)."""

import subprocess  # nosec -- fixed git commands only, no untrusted input

_PYPROJECT_TOML = "pyproject.toml"


def staged_files(*, check: bool) -> list[str]:
    """Get the list of staged file paths.

    Args:
        check: Whether to raise if the underlying git command fails,
            rather than silently continuing with empty output.

    Returns:
        Every file staged for this commit, or an empty list if the
        command failed and a check is False.
    """
    result = subprocess.run(  # nosec
        ["git", "diff", "--cached", "--name-only"],  # noqa: S607
        capture_output=True,
        text=True,
        check=check,
    )
    return result.stdout.splitlines()


def pyproject_version_changed(*, check: bool) -> bool:
    """Check whether pyproject.toml's version line changed in the staged diff.

    Args:
        check: Whether to raise if the underlying git command fails,
            rather than silently continuing with empty output.

    Returns:
        True if a version bump is present in the staged diff.
    """
    result = subprocess.run(  # nosec  # noqa: S603
        ["git", "diff", "--cached", "--", _PYPROJECT_TOML],  # noqa: S607
        capture_output=True,
        text=True,
        check=check,
    )
    return any(line.startswith("+version") for line in result.stdout.splitlines())
