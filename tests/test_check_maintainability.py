"""Tests for the check that turns radon's maintainability ranks into an exit code.

Each test writes fixture modules into a temporary directory and runs the check
as a subprocess, the way the pre-commit hook runs it.
"""

from pathlib import Path

from tests.script_checks import find_script, run_check, write_fixture

_SIMPLE_MODULE = "def add(a: int, b: int) -> int:\n    return a + b\n"
_UNPARSABLE_MODULE = "def broken(:\n"
_TANGLED_BRANCHES = 300
_FAILURE = 1
_SCRIPT = find_script(name="check_maintainability.py")


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


def test_simple_module_passes(*, tmp_path: Path) -> None:
    """A module that ranks A produces no output and no failure."""
    write_fixture(directory=tmp_path, name="simple.py", content=_SIMPLE_MODULE)

    result = run_check(script=_SCRIPT, cwd=tmp_path, arguments=["simple.py"])

    assert not result.exit_code
    assert not result.lines


def test_module_below_a_fails_and_names_it(*, tmp_path: Path) -> None:
    """A module that ranks C fails, and the message names its path, index and rank."""
    write_fixture(directory=tmp_path, name="tangled.py", content=_tangled_module())

    result = run_check(script=_SCRIPT, cwd=tmp_path, arguments=["tangled.py"])

    assert result.exit_code == _FAILURE
    assert result.lines == ["tangled.py: maintainability index 0.0 ranks C, below A"]


def test_allowed_module_below_a_passes(*, tmp_path: Path) -> None:
    """The --allow option lets a module waiting to be split rank below A."""
    write_fixture(directory=tmp_path, name="tangled.py", content=_tangled_module())

    result = run_check(script=_SCRIPT, cwd=tmp_path, arguments=["--allow=tangled.py", "tangled.py"])

    assert not result.exit_code
    assert not result.lines


def test_allow_entry_for_a_module_ranked_a_fails(*, tmp_path: Path) -> None:
    """An entry that is no longer needed fails, so exceptions cannot outlive the split."""
    write_fixture(directory=tmp_path, name="simple.py", content=_SIMPLE_MODULE)

    result = run_check(script=_SCRIPT, cwd=tmp_path, arguments=["--allow=simple.py", "simple.py"])

    assert result.exit_code == _FAILURE
    assert result.lines == ["simple.py: ranks A now, remove its --allow entry"]


def test_allow_entry_for_an_unchecked_file_fails(*, tmp_path: Path) -> None:
    """An entry naming a file the check never saw fails, for example, after a rename."""
    write_fixture(directory=tmp_path, name="simple.py", content=_SIMPLE_MODULE)

    result = run_check(script=_SCRIPT, cwd=tmp_path, arguments=["--allow=renamed.py", "simple.py"])

    assert result.exit_code == _FAILURE
    assert result.lines == ["renamed.py: --allow names a file that is not checked"]


def test_unparsable_module_fails(*, tmp_path: Path) -> None:
    """A module radon cannot parse fails rather than passing unmeasured."""
    write_fixture(directory=tmp_path, name="broken.py", content=_UNPARSABLE_MODULE)

    result = run_check(script=_SCRIPT, cwd=tmp_path, arguments=["broken.py"])

    assert result.exit_code == _FAILURE
    assert len(result.lines) == 1
    assert result.lines[0].startswith("broken.py: radon could not analyse it: ")


def test_no_files_passes_without_running_radon(*, tmp_path: Path) -> None:
    """With no files, the check skips radon, which exits with a usage error when given no paths."""
    result = run_check(script=_SCRIPT, cwd=tmp_path, arguments=[])

    assert not result.exit_code
    assert not result.lines


def test_only_the_unallowed_module_below_a_is_reported(*, tmp_path: Path) -> None:
    """An allowed nested module, an unallowed module and a simple module are each judged on their own."""
    write_fixture(directory=tmp_path, name="sub/allowed.py", content=_tangled_module())
    write_fixture(directory=tmp_path, name="unallowed.py", content=_tangled_module())
    write_fixture(directory=tmp_path, name="simple.py", content=_SIMPLE_MODULE)

    result = run_check(
        script=_SCRIPT,
        cwd=tmp_path,
        arguments=["--allow=sub/allowed.py", "sub/allowed.py", "unallowed.py", "simple.py"],
    )

    assert result.exit_code == _FAILURE
    assert result.lines == ["unallowed.py: maintainability index 0.0 ranks C, below A"]
