"""Tests for scripts/check_definition_of_done.py's version-change detection.

Runs the script itself as a subprocess against a real, throwaway git repo,
rather than importing its internals — scripts/ is not a package, and this
matches REVIEW_CHECKLIST.md's own preference for testing the actual, real
invocation over a convenient proxy for it.
"""

import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).parent.parent / "scripts" / "check_definition_of_done.py"


def _run_git(*, args: list[str], cwd: Path) -> None:
    """Run a fixed git command in a throwaway repo, ignoring its output.

    Args:
        args: The git subcommand and its arguments.
        cwd: The repository to run inside.
    """
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)  # nosec -- fixed args, throwaway test repo


def _init_repo(*, path: Path) -> None:
    """Initialize a throwaway git repo with a committed pyproject.toml and CHANGELOG.md.

    Args:
        path: Where to create the repo.
    """
    _run_git(args=["init"], cwd=path)
    _run_git(args=["config", "user.email", "test@example.com"], cwd=path)
    _run_git(args=["config", "user.name", "Test"], cwd=path)
    (path / "pyproject.toml").write_text('version = "1.0.0"\n')
    (path / "CHANGELOG.md").write_text("# Changelog\n")
    _run_git(args=["add", "."], cwd=path)
    _run_git(args=["commit", "-m", "init"], cwd=path)


def _run_script(*, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run check_definition_of_done.py against a real git repo.

    Args:
        cwd: The git repository to run inside.

    Returns:
        The completed process, with captured stdout.
    """
    return subprocess.run(  # nosec -- fixed script path, throwaway test repo
        [sys.executable, str(_SCRIPT)], cwd=cwd, capture_output=True, text=True, check=True
    )


# pyrigor: 403 # pytest fixture injection, not a real violation
def test_warns_when_version_bumped_without_changelog_entry(tmp_path: Path) -> None:
    """A staged version bump with no staged CHANGELOG.md change should print the reminder.

    This is the actual regression case: the original bug used `--name-only`,
    which can only ever list filenames, never diff content with +/- prefixes,
    so `_pyproject_version_changed()` could never return True — this warning
    had never fired on any commit, ever.
    """
    _init_repo(path=tmp_path)
    (tmp_path / "pyproject.toml").write_text('version = "1.0.1"\n')
    _run_git(args=["add", "pyproject.toml"], cwd=tmp_path)

    result = _run_script(cwd=tmp_path)

    assert "CHANGELOG.md" in result.stdout


# pyrigor: 403 # pytest fixture injection, not a real violation
def test_no_warning_when_version_bump_has_changelog_entry(tmp_path: Path) -> None:
    """A staged version bump with a staged CHANGELOG.md change should not print the reminder."""
    _init_repo(path=tmp_path)
    (tmp_path / "pyproject.toml").write_text('version = "1.0.1"\n')
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 1.0.1\n")
    _run_git(args=["add", "."], cwd=tmp_path)

    result = _run_script(cwd=tmp_path)

    assert "CHANGELOG.md" not in result.stdout


# pyrigor: 403 # pytest fixture injection, not a real violation
def test_no_warning_when_pyproject_unchanged(tmp_path: Path) -> None:
    """No staged pyproject.toml change at all should not print the reminder."""
    _init_repo(path=tmp_path)
    (tmp_path / "README.md").write_text("hello\n")
    _run_git(args=["add", "README.md"], cwd=tmp_path)

    result = _run_script(cwd=tmp_path)

    assert "CHANGELOG.md" not in result.stdout


# pyrigor: 403 # pytest fixture injection, not a real violation
def test_no_warning_when_pyproject_changed_but_not_the_version_line(tmp_path: Path) -> None:
    """A staged pyproject.toml change that isn't the version line should not print the reminder.

    Guards against a naive fix treating any pyproject.toml diff as a version
     bump instead of checking for the actual +version line.
    """
    _init_repo(path=tmp_path)
    (tmp_path / "pyproject.toml").write_text('version = "1.0.0"\ndescription = "changed"\n')
    _run_git(args=["add", "pyproject.toml"], cwd=tmp_path)

    result = _run_script(cwd=tmp_path)

    assert "CHANGELOG.md" not in result.stdout
