"""Wrapper running pip-audit against a fresh uv export.

The pip-audit's own -r flag expects standard requirements.txt syntax,
not uv.lock's 'toml' format, and confirmed directly, does not support
stdin or uv.lock natively via --locked either. So this exports
first, then audits, cleaning up the temp file afterward.
"""

import subprocess  # nosec -- fixed, local uv/pip-audit invocation only
import sys
import tempfile
from pathlib import Path


def _export_and_audit(*, export_path: str) -> subprocess.CompletedProcess[bytes]:
    """Export uv.lock to the requirement file, then audit it, returning pip-audit's own result.

    Args:
        export_path: Where to write the exported requirements file.

    Returns:
        The completed process of the pip-audit, including its exit code.
    """
    subprocess.run(  # nosec  # noqa: S603
        ["uv", "export", "--format", "requirements-txt", "--no-hashes", "-o", export_path],  # noqa: S607
        check=True,
    )
    # noinspection PyArgumentEqualDefault
    return subprocess.run(["pip-audit", "-r", export_path], check=False)  # nosec  # noqa: S603, S607


def main() -> None:
    """Export uv.lock to the requirements.txt format, run pip-audit against it, then clean up."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        export_path = f.name

    try:
        result = _export_and_audit(export_path=export_path)
    finally:
        Path(export_path).unlink(missing_ok=True)

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
