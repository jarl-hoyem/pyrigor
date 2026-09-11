"""Smoke-test the built wheel and source distribution of pyrigor."""

import json
import os
import shutil
import subprocess  # nosec B404 - this script intentionally invokes trusted local uv tooling
import tempfile
import tomllib
from pathlib import Path
from typing import NamedTuple, cast

from jsonschema import validate

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SCHEMA = ROOT / "schemas" / "pyrigor-diagnostics-v1.json"
EXPECTED_ARTIFACT_COUNT = 2
WINDOWS_PLATFORM = "nt"
FIXER_INPUT = "def apply(left, right):\n    ...\n"
FIXER_OUTPUT = "def apply(*, left, right):\n    ...\n"
FIXER_DIFF_LINE = "-def apply(left, right):"


class ArtifactPair(NamedTuple):
    """The wheel and source-distribution artefacts produced by the build."""

    wheel: Path
    sdist: Path


def _uv_executable() -> str:
    """Return the absolute uv executable path used by the smoke test."""
    executable = shutil.which("uv")
    if executable is None:
        raise RuntimeError("uv executable not found on PATH")
    return executable


def _pyproject_version() -> str:
    """Return the project version declared in pyproject.toml."""
    return cast("str", tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"])


def _run_artefact(*, executable: Path, artefact: Path, target: str) -> dict[str, object]:
    """Run the installed artefact against one fixture and return JSON output."""
    command = [
        str(executable),
        target,
        "--output-format",
        "json",
    ]
    # noinspection PyArgumentEqualDefault
    result = subprocess.run(command, check=False, capture_output=True, text=True)  # noqa: S603  # nosec B603
    if result.returncode not in {0, 1}:
        raise RuntimeError(f"{artefact.name} failed for {target}: {result.stderr}")
    output = cast("dict[str, object]", json.loads(result.stdout))
    validate(instance=output, schema=json.loads(SCHEMA.read_text(encoding="utf-8")))
    return output


def _artefact_results(*, artefact: Path, environment: Path) -> dict[str, dict[str, object]]:
    """Collect smoke-test results for one artefact."""
    targets = {
        "clean": "manual-tests/cli/clean.py",
        "violations": "manual-tests/cli/violations.py",
        "suppressed": "manual-tests/cli/suppressed.py",
        "operational-error": "manual-tests/cli/parse-error.ps1",
    }
    executable_name = "pyrigor.exe" if os.name == WINDOWS_PLATFORM else "pyrigor"
    executable = environment / ("Scripts" if os.name == WINDOWS_PLATFORM else "bin") / executable_name
    _run_version_smoke(executable=executable, artefact=artefact)
    results = {
        name: _run_artefact(executable=executable, artefact=artefact, target=target) for name, target in targets.items()
    }
    _run_fixer_smoke(executable=executable, artefact=artefact, fixture=environment / "fixer-fixture.py")
    return results


def _run_version_smoke(*, executable: Path, artefact: Path) -> None:
    """Verify the installed entry point reports the packaged version."""
    expected = f"pyrigor {_pyproject_version()}"
    # noinspection PyArgumentEqualDefault
    result = subprocess.run(  # noqa: S603  # nosec B603 - trusted local executable
        [str(executable), "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    reported = result.stdout.strip()
    if result.returncode or reported != expected:
        raise RuntimeError(f"{artefact.name} reported {reported!r}, expected {expected!r}")


def _run_fixer_smoke(*, executable: Path, artefact: Path, fixture: Path) -> None:
    """Verify the installed entry point applies and previews a PYR402 fix."""
    fixture.write_text(FIXER_INPUT, encoding="utf-8", newline="")
    # noinspection PyArgumentEqualDefault
    fix = subprocess.run(  # noqa: S603  # nosec B603 - trusted local executable and temporary fixture
        [str(executable), "--fix", "--select", "PYR402", str(fixture)],
        check=False,
        capture_output=True,
        text=True,
    )
    if fix.returncode or fixture.read_text(encoding="utf-8") != FIXER_OUTPUT:
        raise RuntimeError(f"{artefact.name} fixer failed: {fix.stderr}")
    fixture.write_text(FIXER_INPUT, encoding="utf-8", newline="")
    _run_fixer_diff(executable=executable, artefact=artefact, fixture=fixture)


def _run_fixer_diff(*, executable: Path, artefact: Path, fixture: Path) -> None:
    """Verify the installed entry point previews a fix without writing."""
    # noinspection PyArgumentEqualDefault
    diff = subprocess.run(  # noqa: S603  # nosec B603 - trusted local executable and temporary fixture
        [str(executable), "--diff", "--select=PYR402", str(fixture)],
        check=False,
        capture_output=True,
        text=True,
    )
    if diff.returncode or fixture.read_text(encoding="utf-8") != FIXER_INPUT or FIXER_DIFF_LINE not in diff.stdout:
        raise RuntimeError(f"{artefact.name} fixer diff failed: {diff.stderr}")


def _install_artefact(*, artefact: Path, environment: Path) -> None:
    """Create an isolated environment and install one artefact into it."""
    subprocess.run(  # noqa: S603  # nosec B603 - trusted local uv executable
        [_uv_executable(), "venv", str(environment)], cwd=ROOT, check=True, capture_output=True, text=True
    )
    python = (
        environment
        / ("Scripts" if os.name == WINDOWS_PLATFORM else "bin")
        / ("python.exe" if os.name == WINDOWS_PLATFORM else "python")
    )
    subprocess.run(  # noqa: S603  # nosec B603 - trusted local uv executable
        [_uv_executable(), "pip", "install", "--python", str(python), str(artefact)], cwd=ROOT, check=True
    )


def _build_artefacts() -> ArtifactPair:
    """Build the distributions and return the wheel and source archive."""
    # Remove stale releases so the artefact count below describes this build.
    if DIST.exists():
        shutil.rmtree(DIST)
    subprocess.run([_uv_executable(), "build"], cwd=ROOT, check=True)  # noqa: S603  # nosec B603
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    artefacts = sorted(DIST.glob(f"pyrigor-{version}*.whl")) + sorted(DIST.glob(f"pyrigor-{version}*.tar.gz"))
    if len(artefacts) != EXPECTED_ARTIFACT_COUNT:
        raise RuntimeError(f"Expected one wheel and one source distribution, found: {artefacts}")
    return ArtifactPair(wheel=artefacts[0], sdist=artefacts[1])


def _compare_artefacts(*, wheel: Path, sdist: Path) -> None:
    """Install both artefacts and require identical smoke-test results."""
    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_root = Path(temporary_directory)
        wheel_environment = temporary_root / "wheel-env"
        sdist_environment = temporary_root / "sdist-env"
        _install_artefact(artefact=wheel, environment=wheel_environment)
        _install_artefact(artefact=sdist, environment=sdist_environment)
        wheel_results = _artefact_results(artefact=wheel, environment=wheel_environment)
        sdist_results = _artefact_results(artefact=sdist, environment=sdist_environment)
    if wheel_results != sdist_results:
        raise RuntimeError("Wheel and source distribution produced different smoke-test results")


def main() -> None:
    """Build and compare wheel and source-distribution smoke-test results."""
    artefacts = _build_artefacts()
    _compare_artefacts(wheel=artefacts.wheel, sdist=artefacts.sdist)


if __name__ == "__main__":
    main()
