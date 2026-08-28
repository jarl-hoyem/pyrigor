"""Smoke-test the built wheel and source distribution of pyrigor."""

import json
import os
import shutil
import subprocess  # nosec B404 - this script intentionally invokes trusted local uv tooling
import tempfile
from pathlib import Path
from typing import NamedTuple, cast

from jsonschema import validate

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SCHEMA = ROOT / "schemas" / "pyrigor-diagnostics-v1.json"
EXPECTED_ARTIFACT_COUNT = 2
WINDOWS_PLATFORM = "nt"


class ArtifactPair(NamedTuple):
    """The wheel and source-distribution artifacts produced by the build."""

    wheel: Path
    sdist: Path


def _uv_executable() -> str:
    """Return the absolute uv executable path used by the smoke test."""
    executable = shutil.which("uv")
    if executable is None:
        raise RuntimeError("uv executable not found on PATH")
    return executable


def _run_artifact(*, executable: Path, artifact: Path, target: str) -> dict[str, object]:
    """Run the installed artifact against one fixture and return JSON output."""
    command = [
        str(executable),
        target,
        "--output-format",
        "json",
    ]
    # noinspection PyArgumentEqualDefault
    result = subprocess.run(command, check=False, capture_output=True, text=True)  # noqa: S603  # nosec B603
    if result.returncode not in {0, 1}:
        raise RuntimeError(f"{artifact.name} failed for {target}: {result.stderr}")
    output = cast("dict[str, object]", json.loads(result.stdout))
    validate(instance=output, schema=json.loads(SCHEMA.read_text(encoding="utf-8")))
    return output


def _artifact_results(*, artifact: Path, environment: Path) -> dict[str, dict[str, object]]:
    """Collect smoke-test results for one artifact."""
    targets = {
        "clean": "manual-tests/cli/clean.py",
        "violations": "manual-tests/cli/violations.py",
        "suppressed": "manual-tests/cli/suppressed.py",
        "operational-error": "manual-tests/cli/parse-error.ps1",
    }
    executable_name = "pyrigor.exe" if os.name == WINDOWS_PLATFORM else "pyrigor"
    executable = environment / ("Scripts" if os.name == WINDOWS_PLATFORM else "bin") / executable_name
    return {
        name: _run_artifact(executable=executable, artifact=artifact, target=target) for name, target in targets.items()
    }


def _install_artifact(*, artifact: Path, environment: Path) -> None:
    """Create an isolated environment and install one artifact into it."""
    subprocess.run(  # noqa: S603  # nosec B603 - trusted local uv executable
        [_uv_executable(), "venv", str(environment)], cwd=ROOT, check=True, capture_output=True, text=True
    )
    python = (
        environment
        / ("Scripts" if os.name == WINDOWS_PLATFORM else "bin")
        / ("python.exe" if os.name == WINDOWS_PLATFORM else "python")
    )
    subprocess.run(  # noqa: S603  # nosec B603 - trusted local uv executable
        [_uv_executable(), "pip", "install", "--python", str(python), str(artifact)], cwd=ROOT, check=True
    )


def _build_artifacts() -> ArtifactPair:
    """Build the distributions and return the wheel and source archive."""
    subprocess.run([_uv_executable(), "build"], cwd=ROOT, check=True)  # noqa: S603  # nosec B603
    artifacts = sorted(DIST.glob("pyrigor-*.whl")) + sorted(DIST.glob("pyrigor-*.tar.gz"))
    if len(artifacts) != EXPECTED_ARTIFACT_COUNT:
        raise RuntimeError(f"Expected one wheel and one source distribution, found: {artifacts}")
    return ArtifactPair(wheel=artifacts[0], sdist=artifacts[1])


def _compare_artifacts(*, wheel: Path, sdist: Path) -> None:
    """Install both artifacts and require identical smoke-test results."""
    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_root = Path(temporary_directory)
        wheel_environment = temporary_root / "wheel-env"
        sdist_environment = temporary_root / "sdist-env"
        _install_artifact(artifact=wheel, environment=wheel_environment)
        _install_artifact(artifact=sdist, environment=sdist_environment)
        wheel_results = _artifact_results(artifact=wheel, environment=wheel_environment)
        sdist_results = _artifact_results(artifact=sdist, environment=sdist_environment)
    if wheel_results != sdist_results:
        raise RuntimeError("Wheel and source distribution produced different smoke-test results")


def main() -> None:
    """Build and compare wheel and source-distribution smoke-test results."""
    artifacts = _build_artifacts()
    _compare_artifacts(wheel=artifacts.wheel, sdist=artifacts.sdist)


if __name__ == "__main__":
    main()
