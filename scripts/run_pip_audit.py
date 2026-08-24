"""Wrapper running pip-audit against a fresh uv export.

The pip-audit's own -r flag expects standard requirements.txt syntax,
not uv.lock's 'toml' format, so this exports first, then audits.
"""

import subprocess  # nosec -- fixed, local uv/pip-audit invocation only
import sys
import tempfile


def main() -> None:
    """Export uv.lock to the requirements.txt format, then run pip-audit against it."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        export_path = f.name

    subprocess.run(  # nosec  # noqa: S603
        ["uv", "export", "--format", "requirements-txt", "--no-hashes", "-o", export_path],  # noqa: S607
        check=True,
    )
    # noinspection PyArgumentEqualDefault
    result = subprocess.run(["pip-audit", "-r", export_path], check=False)  # nosec  # noqa: S603, S607
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
