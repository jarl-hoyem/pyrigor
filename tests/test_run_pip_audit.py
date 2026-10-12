"""Tests for the locked development dependency export used by pip-audit."""

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Final
from unittest.mock import MagicMock

import pytest

_UV_EXPORT: Final = "export"


def _load_script() -> ModuleType:
    """Load scripts/run_pip_audit.py as a module."""
    path = Path(__file__).parents[1] / "scripts" / "run_pip_audit.py"
    spec = importlib.util.spec_from_file_location("run_pip_audit", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_export_command(*, command: list[str], export_path: Path) -> None:
    """Check that the wrapper selects the locked development extra."""
    assert command[1] == _UV_EXPORT
    assert command[2:4] == ["--format", "requirements-txt"]
    assert command[4:8] == ["--no-hashes", "--extra", "dev", "--locked"]
    assert command[8:] == ["-o", str(export_path)]


def test_export_and_audit_includes_locked_development_dependencies(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The audit input includes the locked optional dev extra, not only the project itself."""
    module = _load_script()
    export_path = tmp_path / "requirements.txt"
    export_path.write_text("ruff==0.16.10\nbandit==1.9.4\nmypy==2.4.0\n", encoding="utf-8")
    assert {"ruff", "bandit", "mypy"} <= {
        line.partition("==")[0] for line in export_path.read_text(encoding="utf-8").splitlines()
    }
    runner = MagicMock(side_effect=[SimpleNamespace(returncode=0), SimpleNamespace(returncode=0)])

    temporary_file = MagicMock()
    temporary_file.__enter__.return_value.name = str(export_path)
    monkeypatch.setattr(module.tempfile, "NamedTemporaryFile", MagicMock(return_value=temporary_file))
    monkeypatch.setattr(module.subprocess, "run", runner)

    with pytest.raises(SystemExit) as caught:
        module.main()

    assert not caught.value.code
    _assert_export_command(command=runner.call_args_list[0].args[0], export_path=export_path)
    assert runner.call_args_list[1].args[0] == ["pip-audit", "-r", str(export_path)]
