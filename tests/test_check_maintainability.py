"""Tests for the check that turns radon's maintainability ranks into an exit code.

Each test writes fixture modules into a temporary directory and runs the check
as a subprocess, the way the pre-commit hook runs it.
"""

import subprocess  # nosec B404 -- test runs the maintainability check script
import sys
from pathlib import Path
from typing import NamedTuple

_SIMPLE_MODULE = "def add(a: int, b: int) -> int:\n    return a + b\n"
_UNPARSABLE_MODULE = "def broken(:\n"
_TANGLED_BRANCHES = 300
_FAILURE = 1


class CheckResult(NamedTuple):
    """The check's exit code and the lines it printed."""

    exit_code: int
    lines: list[str]


def _check_path() -> Path:
    """Return the check script, whether run from the repository or a copy under mutants/."""
    for parent in Path(__file__).parents:
        candidate = parent / "scripts" / "check_maintainability.py"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("scripts/check_maintainability.py")


def _tangled_module() -> str:
    """Return a module whose maintainability index ranks C."""
    body = [
        line
        for index in range(_TANGLED_BRANCHES)
        for line in (
            f"    if a * {index} + b ** 2 - c / (d + {index + 1}) > {index} and (a % {index + 7} or b ^ {index}):",
            f"        total += (a * b - c * d + {index}) // ({index} + 1) - (a << 2) + (b >> 1) * {index}",
        )
    ]
    return "\n".join(["def tangled(a, b, c, d):", "    total = 0", *body, "    return total"]) + "\n"


def _write(*, directory: Path, name: str, content: str) -> None:
    """Write one fixture module, creating its parent directories."""
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run(*, cwd: Path, arguments: list[str]) -> CheckResult:
    """Run the check with the given arguments inside the fixture directory."""
    # ruff PLW1510 and pylint W1510 require an explicit check argument.
    # noinspection PyArgumentEqualDefault
    result = subprocess.run(  # nosec B603 # noqa: S603 -- the check script with fixed test arguments
        [sys.executable, str(_check_path()), *arguments],
        cwd=cwd,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    return CheckResult(exit_code=result.returncode, lines=result.stdout.splitlines())


def test_simple_module_passes(*, tmp_path: Path) -> None:
    """A module that ranks A produces no output and no failure."""
    _write(directory=tmp_path, name="simple.py", content=_SIMPLE_MODULE)

    result = _run(cwd=tmp_path, arguments=["simple.py"])

    assert not result.exit_code
    assert not result.lines


def test_module_below_a_fails_and_names_it(*, tmp_path: Path) -> None:
    """A module that ranks C fails, and the message names its path, index and rank."""
    _write(directory=tmp_path, name="tangled.py", content=_tangled_module())

    result = _run(cwd=tmp_path, arguments=["tangled.py"])

    assert result.exit_code == _FAILURE
    assert result.lines == ["tangled.py: maintainability index 0.0 ranks C, below A"]


def test_allowed_module_below_a_passes(*, tmp_path: Path) -> None:
    """The --allow option lets a module waiting to be split rank below A."""
    _write(directory=tmp_path, name="tangled.py", content=_tangled_module())

    result = _run(cwd=tmp_path, arguments=["--allow=tangled.py", "tangled.py"])

    assert not result.exit_code
    assert not result.lines


def test_allow_entry_for_a_module_ranked_a_fails(*, tmp_path: Path) -> None:
    """An entry that is no longer needed fails, so exceptions cannot outlive the split."""
    _write(directory=tmp_path, name="simple.py", content=_SIMPLE_MODULE)

    result = _run(cwd=tmp_path, arguments=["--allow=simple.py", "simple.py"])

    assert result.exit_code == _FAILURE
    assert result.lines == ["simple.py: ranks A now, remove its --allow entry"]


def test_allow_entry_for_an_unchecked_file_fails(*, tmp_path: Path) -> None:
    """An entry naming a file the check never saw fails, for example, after a rename."""
    _write(directory=tmp_path, name="simple.py", content=_SIMPLE_MODULE)

    result = _run(cwd=tmp_path, arguments=["--allow=renamed.py", "simple.py"])

    assert result.exit_code == _FAILURE
    assert result.lines == ["renamed.py: --allow names a file that is not checked"]


def test_unparsable_module_fails(*, tmp_path: Path) -> None:
    """A module radon cannot parse fails rather than passing unmeasured."""
    _write(directory=tmp_path, name="broken.py", content=_UNPARSABLE_MODULE)

    result = _run(cwd=tmp_path, arguments=["broken.py"])

    assert result.exit_code == _FAILURE
    assert len(result.lines) == 1
    assert result.lines[0].startswith("broken.py: radon could not analyse it: ")


def test_no_files_passes_without_running_radon(*, tmp_path: Path) -> None:
    """With no files, the check skips radon, which exits with a usage error when given no paths."""
    result = _run(cwd=tmp_path, arguments=[])

    assert not result.exit_code
    assert not result.lines


def test_only_the_unallowed_module_below_a_is_reported(*, tmp_path: Path) -> None:
    """An allowed nested module, an unallowed module and a simple module are each judged on their own."""
    _write(directory=tmp_path, name="sub/allowed.py", content=_tangled_module())
    _write(directory=tmp_path, name="unallowed.py", content=_tangled_module())
    _write(directory=tmp_path, name="simple.py", content=_SIMPLE_MODULE)

    result = _run(cwd=tmp_path, arguments=["--allow=sub/allowed.py", "sub/allowed.py", "unallowed.py", "simple.py"])

    assert result.exit_code == _FAILURE
    assert result.lines == ["unallowed.py: maintainability index 0.0 ranks C, below A"]
