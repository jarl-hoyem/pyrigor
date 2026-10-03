"""Run Git and the scripts under test in fixture repositories without the invoking repository's Git context.

Git sets repository-local variables such as GIT_DIR and GIT_INDEX_FILE for a hook. A child process that inherits them
works on the invoking repository whatever its working directory is, so a fixture must start from a clean environment.
"""

import functools
import os
import shutil
import subprocess  # nosec B404 -- runs git and the scripts under test in throwaway repositories
from pathlib import Path
from typing import TypeAlias

FixtureResult: TypeAlias = subprocess.CompletedProcess[str]

# Git documents GIT_CONFIG_COUNT together with numbered keys and values, which its own list does not name.
_NUMBERED_CONFIG_PREFIXES = ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")


@functools.cache
def _repository_local_variables() -> frozenset[str]:
    """Ask Git which environment variables it treats as repository-local."""
    git = shutil.which("git")
    assert git is not None
    listing = subprocess.run(  # nosec B603 # noqa: S603 -- fixed git arguments, executable resolved by shutil.which
        [git, "rev-parse", "--local-env-vars"],
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    return frozenset(listing.stdout.split())


def fixture_environment() -> dict[str, str]:
    """Return the current environment without the variables that tie a process to the invoking repository."""
    local = _repository_local_variables()
    return {
        name: value
        for name, value in os.environ.items()
        if name not in local and not name.startswith(_NUMBERED_CONFIG_PREFIXES)
    }


def run_command(*, command: list[str], cwd: Path, environment: dict[str, str]) -> FixtureResult:
    """Run a command with exactly the given environment, capturing its output as UTF-8 text."""
    return subprocess.run(  # nosec B603 # noqa: S603 -- git, pytest and the scripts under test, with fixed arguments
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )


def run_in_fixture(*, command: list[str], cwd: Path) -> FixtureResult:
    """Run a command in a fixture repository, cut off from the repository that runs the tests."""
    return run_command(command=command, cwd=cwd, environment=fixture_environment())
