"""Tests for the whole-project tool exclusion check."""

import subprocess  # nosec B404 -- test invokes a fixed local checker script
import sys
from pathlib import Path
from typing import NamedTuple

_COMPLETE = ".venv,dist,htmlcov,pyrigor.egg-info,mutants,__pycache__"
_WITHOUT_MUTANTS = ".venv,dist,htmlcov,pyrigor.egg-info,__pycache__"
_COMPLETE_PYRIGHT = (
    '[tool.pyright]\nexclude = [".venv", "dist", "htmlcov", "**/__pycache__", "**/*.egg-info", "mutants"]\n'
)
_PYRIGHT_WITHOUT_MUTANTS = '[tool.pyright]\nexclude = [".venv", "dist", "htmlcov", "**/__pycache__", "**/*.egg-info"]\n'
_TOKEN_COUNT = 6


class CheckerResult(NamedTuple):
    """The checker's exit code and the lines it printed."""

    exit_code: int
    lines: list[str]


def _checker_path() -> Path:
    """Return the checker script, whether run from the repository or a copy under mutants/."""
    for parent in Path(__file__).parents:
        candidate = parent / "scripts" / "check_tool_exclusions.py"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("scripts/check_tool_exclusions.py")


def _config(*, radon: str = _COMPLETE, mypy_flag: str = "--exclude-gitignore", radon_comment: str = "") -> str:
    """Build a pre-commit configuration holding the four hooks the checker inspects."""
    return (
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: vulture\n"
        f'        args: [".", "--exclude", "manual-tests,{_COMPLETE}"]\n'
        "      - id: mypy\n"
        f'        args: [".", "{mypy_flag}"]\n'
        "      - id: radon-maintainability\n"
        f"{radon_comment}"
        f'        args: ["--min", "A", ".", "--ignore", "{radon}"]\n'
        "      - id: xenon\n"
        f"        args: [--ignore={_COMPLETE}, .]\n"
    )


def _run(*, cwd: Path, config: str | None = None, pyproject: str | None = None) -> CheckerResult:
    """Write the two files when given, run the checker in that directory and capture its result."""
    if config is not None:
        (cwd / ".pre-commit-config.yaml").write_text(config, encoding="utf-8")
    if pyproject is not None:
        (cwd / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    # noinspection PyArgumentEqualDefault
    result = subprocess.run(  # nosec B603 -- executes the repository's fixed checker script # noqa: S603
        [sys.executable, str(_checker_path())],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )
    return CheckerResult(exit_code=result.returncode, lines=result.stdout.splitlines())


def test_complete_configuration_passes(*, tmp_path: Path) -> None:
    """Every tool excluding the full set is reported as in sync."""
    result = _run(cwd=tmp_path, config=_config(), pyproject=_COMPLETE_PYRIGHT)

    assert not result.exit_code
    assert not result.lines


def test_hook_missing_a_token_fails_and_names_it(*, tmp_path: Path) -> None:
    """A literal-list hook without one directory is reported by hook and directory."""
    result = _run(cwd=tmp_path, config=_config(radon=_WITHOUT_MUTANTS), pyproject=_COMPLETE_PYRIGHT)

    assert result.exit_code == 1
    assert result.lines == ["radon-maintainability does not exclude mutants"]


def test_token_only_in_a_comment_does_not_count(*, tmp_path: Path) -> None:
    """A directory named in a comment inside the hook is not an exclusion."""
    config = _config(radon=_WITHOUT_MUTANTS, radon_comment="        # mutants is excluded elsewhere\n")
    result = _run(cwd=tmp_path, config=config, pyproject=_COMPLETE_PYRIGHT)

    assert result.exit_code == 1
    assert result.lines == ["radon-maintainability does not exclude mutants"]


def test_pyright_missing_a_token_fails_and_names_it(*, tmp_path: Path) -> None:
    """A pyright exclude list without one directory is reported."""
    result = _run(cwd=tmp_path, config=_config(), pyproject=_PYRIGHT_WITHOUT_MUTANTS)

    assert result.exit_code == 1
    assert result.lines == ["pyright does not exclude mutants"]


def test_missing_pyright_table_reports_every_token(*, tmp_path: Path) -> None:
    """A pyproject.toml with no pyright table misses the whole set, not nothing."""
    result = _run(cwd=tmp_path, config=_config(), pyproject='[project]\nname = "x"\n')

    assert result.exit_code == 1
    assert len(result.lines) == _TOKEN_COUNT
    assert all(line.startswith("pyright does not exclude ") for line in result.lines)


def test_mypy_without_gitignore_flag_fails(*, tmp_path: Path) -> None:
    """A mypy hook that no longer reads .gitignore is reported."""
    result = _run(cwd=tmp_path, config=_config(mypy_flag="--strict"), pyproject=_COMPLETE_PYRIGHT)

    assert result.exit_code == 1
    assert result.lines == ["mypy does not pass --exclude-gitignore"]


def test_removed_hook_reports_every_token(*, tmp_path: Path) -> None:
    """A literal-list hook deleted from the configuration fails for the whole set."""
    config = _config().replace("      - id: xenon\n", "      - id: something-else\n")
    result = _run(cwd=tmp_path, config=config, pyproject=_COMPLETE_PYRIGHT)

    assert result.exit_code == 1
    assert len(result.lines) == _TOKEN_COUNT
    assert all(line.startswith("xenon does not exclude ") for line in result.lines)


def test_the_repository_own_configuration_is_in_sync() -> None:
    """The real files this check guards agree with the canonical set."""
    result = _run(cwd=_checker_path().parents[1])

    assert not result.exit_code, result.lines
