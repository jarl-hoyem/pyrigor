"""Tests for the wrapper that runs whole-project tools on git's Python file list.

Each test builds a throwaway git repository and runs the wrapper as a
subprocess. The wrapped tool is Python itself, printing the arguments it
receives, so a test sees exactly which files the wrapper passed on.
"""

import shutil
import subprocess  # nosec B404 -- test runs git and the wrapper script in a throwaway repository
import sys
from pathlib import Path
from typing import NamedTuple

_PRINT_ARGUMENTS = "import sys; sys.stdout.buffer.write(chr(10).join(sys.argv[1:]).encode())"
_TOOL_EXIT_CODE = 3
_EXIT_WITH_TOOL_CODE = f"import sys; sys.exit({_TOOL_EXIT_CODE})"
_USAGE_EXIT_CODE = 2
_NOT_FOUND_EXIT_CODE = 127
_USAGE_PREFIX = "usage:"
_UNKNOWN_TOOL = "no-such-tool-for-pyrigor"
_SKIP_MESSAGE = "No Python files to check."


class WrapperResult(NamedTuple):
    """The wrapper's exit code, the sorted lines it printed and its error output."""

    exit_code: int
    lines: list[str]
    error: str


def _wrapper_path() -> Path:
    """Return the wrapper script, whether run from the repository or a copy under mutants/."""
    for parent in Path(__file__).parents:
        candidate = parent / "scripts" / "run_on_git_python_files.py"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("scripts/run_on_git_python_files.py")


def _run(*, command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a command in the throwaway repository, capturing its output as UTF-8 text."""
    # ruff PLW1510 and pylint W1510 require an explicit check argument.
    # noinspection PyArgumentEqualDefault
    return subprocess.run(  # nosec B603 # noqa: S603 -- git and the wrapper, with fixed test arguments
        command,
        cwd=cwd,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )


def _git(*, args: list[str], cwd: Path) -> None:
    """Run a git command in the throwaway repository, failing the test if git fails."""
    git = shutil.which("git")
    assert git is not None
    _run(command=[git, *args], cwd=cwd).check_returncode()


def _repo(*, path: Path) -> Path:
    """Initialise an empty throwaway git repository and return its path."""
    _git(args=["init", "--quiet"], cwd=path)
    return path


def _wrap(*, cwd: Path, tool: list[str]) -> WrapperResult:
    """Run the wrapper around a tool command inside the repository."""
    result = _run(command=[sys.executable, str(_wrapper_path()), *tool], cwd=cwd)
    return WrapperResult(exit_code=result.returncode, lines=sorted(result.stdout.splitlines()), error=result.stderr)


def test_python_files_git_knows_about_are_passed(*, tmp_path: Path) -> None:
    """Tracked and untracked Python files reach the tool, and other files do not."""
    repo = _repo(path=tmp_path)
    (repo / "tracked.py").write_text("", encoding="utf-8")
    (repo / "untracked.py").write_text("", encoding="utf-8")
    (repo / "notes.txt").write_text("", encoding="utf-8")
    _git(args=["add", "tracked.py"], cwd=repo)

    result = _wrap(cwd=repo, tool=[sys.executable, "-c", _PRINT_ARGUMENTS])

    assert not result.exit_code
    assert result.lines == ["tracked.py", "untracked.py"]


def test_gitignored_directory_is_not_passed(*, tmp_path: Path) -> None:
    """A Python file inside a gitignored directory never reaches the tool."""
    repo = _repo(path=tmp_path)
    (repo / ".gitignore").write_text("mutants/\n", encoding="utf-8")
    (repo / "mutants").mkdir()
    (repo / "mutants" / "copy.py").write_text("", encoding="utf-8")
    (repo / "real.py").write_text("", encoding="utf-8")

    result = _wrap(cwd=repo, tool=[sys.executable, "-c", _PRINT_ARGUMENTS])

    assert result.lines == ["real.py"]


def test_staged_file_deleted_from_disk_is_not_passed(*, tmp_path: Path) -> None:
    """The wrapper skips a staged file deleted from the working tree, since the tool would fail on it."""
    repo = _repo(path=tmp_path)
    (repo / "gone.py").write_text("", encoding="utf-8")
    (repo / "real.py").write_text("", encoding="utf-8")
    _git(args=["add", "gone.py"], cwd=repo)
    (repo / "gone.py").unlink()

    result = _wrap(cwd=repo, tool=[sys.executable, "-c", _PRINT_ARGUMENTS])

    assert result.lines == ["real.py"]


def test_path_with_space_and_non_ascii_characters_is_passed_intact(*, tmp_path: Path) -> None:
    """The file list survives a space and non-ASCII characters without quoting or garbling."""
    repo = _repo(path=tmp_path)
    (repo / "sub dir").mkdir()
    (repo / "sub dir" / "café.py").write_text("", encoding="utf-8")

    result = _wrap(cwd=repo, tool=[sys.executable, "-c", _PRINT_ARGUMENTS])

    assert result.lines == ["sub dir/café.py"]


def test_no_python_files_skips_the_tool(*, tmp_path: Path) -> None:
    """An empty file list skips the tool, which would otherwise fall back to scanning the whole directory."""
    repo = _repo(path=tmp_path)

    result = _wrap(cwd=repo, tool=[sys.executable, "-c", _EXIT_WITH_TOOL_CODE])

    assert not result.exit_code
    assert result.lines == [_SKIP_MESSAGE]


def test_tool_exit_code_is_returned(*, tmp_path: Path) -> None:
    """A failing tool fails the wrapper with the same exit code."""
    repo = _repo(path=tmp_path)
    (repo / "real.py").write_text("", encoding="utf-8")

    result = _wrap(cwd=repo, tool=[sys.executable, "-c", _EXIT_WITH_TOOL_CODE])

    assert result.exit_code == _TOOL_EXIT_CODE


def test_unknown_tool_fails_and_names_it(*, tmp_path: Path) -> None:
    """A tool that is not installed fails clearly rather than silently passing."""
    repo = _repo(path=tmp_path)

    result = _wrap(cwd=repo, tool=[_UNKNOWN_TOOL])

    assert result.exit_code == _NOT_FOUND_EXIT_CODE
    assert _UNKNOWN_TOOL in result.error


def test_no_arguments_prints_usage(*, tmp_path: Path) -> None:
    """Running the wrapper without a tool prints its usage and fails."""
    result = _wrap(cwd=tmp_path, tool=[])

    assert result.exit_code == _USAGE_EXIT_CODE
    assert result.error.startswith(_USAGE_PREFIX)
