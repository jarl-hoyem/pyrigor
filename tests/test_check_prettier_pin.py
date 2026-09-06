"""Tests for the Prettier pin-synchronisation check."""
# pylint: disable=duplicate-code  # Independent subprocess setup is deliberate in this test module.

import json
import subprocess  # nosec B404 -- test invokes a fixed local checker script
import sys
from pathlib import Path
from typing import NamedTuple

_PINNED = "3.9.6"
_BUMPED = "3.10.0"

_CONFIG_TEMPLATE = """repos:
  - repo: local
    hooks:
      - id: prettier
        additional_dependencies: ["prettier@{version}"]
"""


class CheckerResult(NamedTuple):
    """The checker's exit code and what it printed."""

    exit_code: int
    output: str


def _checker_path() -> Path:
    """Return the checker script, whether run from the repository or a mutants copy."""
    checker = Path(__file__).parents[1] / "scripts" / "check_prettier_pin.py"
    if checker.exists():
        return checker
    for parent in Path(__file__).parents[1].parents:
        candidate = parent / "scripts" / "check_prettier_pin.py"
        if candidate.exists():
            return candidate
    return checker


def _run_checker(*, tmp_path: Path, hook_version: str | None, package_version: str | None) -> CheckerResult:
    """Run the checker against a temporary pair of files, returning its exit code and output."""
    config = _CONFIG_TEMPLATE.format(version=hook_version) if hook_version else "repos: []\n"
    package: dict[str, dict[str, str]] = {"devDependencies": {"prettier": package_version}} if package_version else {}
    (tmp_path / ".pre-commit-config.yaml").write_text(config, encoding="utf-8")
    (tmp_path / "package.json").write_text(json.dumps(package), encoding="utf-8")

    # noinspection PyArgumentEqualDefault
    result = subprocess.run(  # nosec B603 -- executes the repository's fixed checker script # noqa: S603
        [sys.executable, str(_checker_path())],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )
    return CheckerResult(exit_code=result.returncode, output=result.stdout)


def test_matching_pins_pass(*, tmp_path: Path) -> None:
    """Both files naming the same version is not a mismatch."""
    result = _run_checker(tmp_path=tmp_path, hook_version=_PINNED, package_version=_PINNED)

    assert not result.exit_code


def test_differing_pins_fail_and_name_both_versions(*, tmp_path: Path) -> None:
    """A version bumped in one file only is reported with both versions."""
    result = _run_checker(tmp_path=tmp_path, hook_version=_PINNED, package_version=_BUMPED)

    assert result.exit_code == 1
    assert _PINNED in result.output
    assert _BUMPED in result.output


def test_hook_pin_absent_fails(*, tmp_path: Path) -> None:
    """A configuration naming no Prettier dependency does not silently pass."""
    result = _run_checker(tmp_path=tmp_path, hook_version=None, package_version=_PINNED)

    assert result.exit_code == 1


def test_package_pin_absent_fails(*, tmp_path: Path) -> None:
    """A package.json naming no Prettier dependency does not silently pass."""
    result = _run_checker(tmp_path=tmp_path, hook_version=_PINNED, package_version=None)

    assert result.exit_code == 1


def test_neither_file_names_prettier_passes(*, tmp_path: Path) -> None:
    """With no pin anywhere there is nothing that can drift."""
    result = _run_checker(tmp_path=tmp_path, hook_version=None, package_version=None)

    assert not result.exit_code


def test_the_repository_own_pins_agree() -> None:
    """The real files this check guards are in agreement."""
    # noinspection PyArgumentEqualDefault
    result = subprocess.run(  # nosec B603 -- executes the repository's fixed checker script # noqa: S603
        [sys.executable, str(_checker_path())],
        capture_output=True,
        text=True,
        cwd=_checker_path().parents[1],
        check=False,
    )

    assert not result.returncode, result.stdout
