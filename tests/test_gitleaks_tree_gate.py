"""Tests that the current-tree Gitleaks gate fails on a planted credential and passes otherwise."""

import secrets
import shutil
import string
from pathlib import Path
from typing import Final

import pytest

from tests.git_isolation import FixtureResult, run_in_fixture

_REPOSITORY_ROOT: Final = Path(__file__).resolve().parent.parent
_CONFIGURATION_FILES: Final = (".pre-commit-config.yaml", ".gitleaks.toml")
_GATE_ARGUMENTS: Final = ["run", "gitleaks-tree", "--all-files", "--hook-stage", "manual"]
_RULE_ID: Final = "github-pat"
_ALPHABET: Final = string.ascii_letters + string.digits
_TOKEN_LENGTH: Final = 36


def _planted_token() -> str:
    """Build a GitHub-style token at run time, so no detectable credential sits in the source tree."""
    return "ghp" + "_" + "".join(secrets.choice(_ALPHABET) for _ in range(_TOKEN_LENGTH))


def _plant(*, directory: Path, names: list[str], token: str) -> None:
    """Write the token into each named file, creating any folders on the way."""
    for name in names:
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f'github_token = "{token}"\n')


def _build_repository(*, directory: Path, token: str, committed: list[str], loose: list[str]) -> None:
    """Build a disposable repository with the repository's own configuration and a planted token.

    Args:
        directory: An empty directory for the disposable repository.
        token: The credential to plant.
        committed: Files that hold the token and are committed.
        loose: Files that hold the token and are left untracked and unstaged.
    """
    for name in _CONFIGURATION_FILES:
        shutil.copyfile(_REPOSITORY_ROOT / name, directory / name)
    (directory / "clean.py").write_text("value = 1\n")
    _plant(directory=directory, names=committed, token=token)
    for command in (["git", "init", "-q"], ["git", "add", "-A"]):
        run_in_fixture(command=command, cwd=directory)
    run_in_fixture(
        command=["git", "-c", "user.name=T", "-c", "user.email=t@example.com", "commit", "-qm", "init"],
        cwd=directory,
    )
    _plant(directory=directory, names=loose, token=token)


def _scan(*, directory: Path) -> FixtureResult:
    """Run the current-tree gate in a disposable repository."""
    pre_commit = shutil.which("pre-commit")
    if pre_commit is None:
        pytest.skip("pre-commit is not installed")
    return run_in_fixture(command=[pre_commit, *_GATE_ARGUMENTS], cwd=directory)


@pytest.mark.slow
def test_clean_tree_passes(*, tmp_path: Path) -> None:
    """A tree with no credential passes the gate."""
    _build_repository(directory=tmp_path, token=_planted_token(), committed=[], loose=[])

    result = _scan(directory=tmp_path)

    assert not result.returncode
    assert _RULE_ID not in result.stdout


@pytest.mark.slow
def test_unstaged_untracked_credential_fails_and_is_redacted(*, tmp_path: Path) -> None:
    """A credential in a file Git does not track yet fails the gate, and the output does not repeat it."""
    token = _planted_token()
    _build_repository(directory=tmp_path, token=token, committed=[], loose=["loose.txt"])

    result = _scan(directory=tmp_path)

    assert result.returncode
    assert _RULE_ID in result.stdout
    assert token not in result.stdout + result.stderr


@pytest.mark.slow
def test_committed_credential_fails(*, tmp_path: Path) -> None:
    """A credential in a committed file fails the gate."""
    _build_repository(directory=tmp_path, token=_planted_token(), committed=["committed.txt"], loose=[])

    result = _scan(directory=tmp_path)

    assert result.returncode
    assert _RULE_ID in result.stdout


@pytest.mark.slow
def test_credential_in_a_tool_directory_is_not_scanned(*, tmp_path: Path) -> None:
    """Third-party directories such as .venv are allowlisted, so a credential passes."""
    _build_repository(directory=tmp_path, token=_planted_token(), committed=[], loose=[".venv/lib/package.txt"])

    result = _scan(directory=tmp_path)

    assert not result.returncode
    assert _RULE_ID not in result.stdout
