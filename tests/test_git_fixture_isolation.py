"""A fixture repository must leave the repository that runs the tests alone.

Git sets repository-local variables for a hook, and a hook in a linked worktree gets GIT_DIR. These tests build a
disposable victim repository, point such a context at it and run the real fixture tests. The victim must come out
byte for byte as it went in.
"""

import sys
from pathlib import Path
from typing import NamedTuple

import pytest

from tests.git_isolation import fixture_environment, run_command, run_in_fixture

_TESTS = Path(__file__).parent
_FIXTURE_TEST_FILES = [
    str(_TESTS / "test_run_on_git_python_files.py"),
    str(_TESTS / "test_check_definition_of_done.py"),
]
_NUMBERED_KEY = "GIT_CONFIG_KEY_0"
_NUMBERED_VALUE = "GIT_CONFIG_VALUE_0"
_UNRELATED = "GIT_EDITOR"
_UNRELATED_VALUE = "true"
_PATH_NAMES = ("PATH", "Path")


class _Victim(NamedTuple):
    """A disposable repository with a linked worktree, standing in for the repository that runs the hook."""

    worktree: Path
    git_dir: Path


def _git(*, args: list[str], cwd: Path) -> None:
    """Run git in a disposable repository without any inherited context, failing the test if git fails."""
    run_in_fixture(command=["git", *args], cwd=cwd).check_returncode()


def _git_output(*, args: list[str], cwd: Path) -> str:
    """Run git in a disposable repository without any inherited context and return its output."""
    result = run_in_fixture(command=["git", *args], cwd=cwd)
    result.check_returncode()
    return result.stdout


def _build_victim(*, root: Path) -> _Victim:
    """Create a repository with one commit and a linked worktree with a second commit and an index of its own."""
    main = root / "victim"
    main.mkdir()
    _git(args=["init", "--quiet"], cwd=main)
    _git(args=["config", "user.email", "victim@example.com"], cwd=main)
    _git(args=["config", "user.name", "Victim"], cwd=main)
    (main / "real.py").write_text("real = 1\n", encoding="utf-8")
    _git(args=["add", "real.py"], cwd=main)
    _git(args=["commit", "--quiet", "-m", "victim: first"], cwd=main)
    worktree = root / "victim-worktree"
    _git(args=["worktree", "add", "--quiet", str(worktree), "-b", "feature"], cwd=main)
    (worktree / "feature.py").write_text("feature = 2\n", encoding="utf-8")
    _git(args=["add", "feature.py"], cwd=worktree)
    _git(args=["commit", "--quiet", "-m", "victim: feature work"], cwd=worktree)
    return _Victim(
        worktree=worktree, git_dir=Path(_git_output(args=["rev-parse", "--absolute-git-dir"], cwd=worktree).strip())
    )


def _state(*, victim: _Victim) -> dict[str, object]:
    """Read everything the isolation must leave alone, without changing the victim.

    That is the index, HEAD, every commit, the local configuration and the working files.
    """
    worktree = victim.worktree
    return {
        "index": (victim.git_dir / "index").read_bytes(),
        "head": _git_output(args=["rev-parse", "HEAD"], cwd=worktree),
        "commits": _git_output(args=["log", "--all", "--format=%H"], cwd=worktree),
        "config": _git_output(args=["config", "--local", "--list"], cwd=worktree),
        "files": {path.name: path.read_bytes() for path in sorted(worktree.iterdir()) if path.is_file()},
    }


def _context(*, name: str, victim: _Victim) -> dict[str, str]:
    """Return the variables Git sets for a hook: GIT_DIR in a linked worktree, or the index of the commit stage."""
    contexts = {
        "hook-in-a-linked-worktree": {"GIT_DIR": str(victim.git_dir)},
        "commit-stage-index": {"GIT_INDEX_FILE": str(victim.git_dir / "index")},
        "git-dir-with-work-tree": {"GIT_DIR": str(victim.git_dir), "GIT_WORK_TREE": str(victim.worktree)},
    }
    return contexts[name]


@pytest.mark.parametrize("name", ["hook-in-a-linked-worktree", "commit-stage-index", "git-dir-with-work-tree"])
def test_the_fixture_tests_leave_the_invoking_repository_alone(*, tmp_path: Path, name: str) -> None:
    """The fixture tests run as a child of a hook, so the context they inherit points at the victim."""
    victim = _build_victim(root=tmp_path)
    before = _state(victim=victim)
    # The child gets a basetemp of its own: pytest empties its base directory, and the parent may be using one.
    options = ["-q", "-p", "no:cacheprovider", "-o", "addopts=", f"--basetemp={tmp_path / 'child'}"]
    environment = {**fixture_environment(), **_context(name=name, victim=victim), "PYTEST_ADDOPTS": ""}
    result = run_command(
        command=[sys.executable, "-m", "pytest", *options, *_FIXTURE_TEST_FILES],
        cwd=_TESTS.parent,
        environment=environment,
    )
    assert not result.returncode, result.stdout[-1500:]
    assert _state(victim=victim) == before


def test_the_fixture_environment_drops_every_variable_git_lists(*, monkeypatch: pytest.MonkeyPatch) -> None:
    """Git names its repository-local variables itself, so no hand-written list can fall behind."""
    listed = run_in_fixture(command=["git", "rev-parse", "--local-env-vars"], cwd=_TESTS).stdout.split()
    for variable in listed:
        monkeypatch.setenv(variable, "inherited")
    environment = fixture_environment()
    assert listed
    assert not set(listed) & set(environment)


def test_the_fixture_environment_drops_numbered_config_and_keeps_the_rest(*, monkeypatch: pytest.MonkeyPatch) -> None:
    """GIT_CONFIG_KEY_n and GIT_CONFIG_VALUE_n belong to GIT_CONFIG_COUNT. Unrelated variables stay."""
    monkeypatch.setenv(_NUMBERED_KEY, "user.name")
    monkeypatch.setenv(_NUMBERED_VALUE, "Inherited")
    monkeypatch.setenv(_UNRELATED, _UNRELATED_VALUE)
    environment = fixture_environment()
    assert (_NUMBERED_KEY in environment, _NUMBERED_VALUE in environment) == (False, False)
    assert environment[_UNRELATED] == _UNRELATED_VALUE
    assert any(name in environment for name in _PATH_NAMES)
