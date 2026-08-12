"""Command-line entry point for pyrigor's checkers."""

import sys
from pathlib import Path

from pyrigor.checkers import find_pyr003_violations


def main(paths: list[str]) -> int:
    """Run all checkers against the given file paths.

    Args:
        paths: File paths to check.

    Returns:
        0 if no violations were found, 1 otherwise.
    """
    exit_code = 0

    for path in paths:
        source = Path(path).read_text(encoding="utf-8")
        violations = find_pyr003_violations(source)

        for violation in violations:
            print(f"{path}:{violation.line}:{violation.column}: PYR003 {violation.message}")
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))  # pragma: no cover
