"""Command-line entry point for pyrigor's checkers."""

import ast
import sys
import time
from collections import Counter
from importlib.metadata import version
from pathlib import Path

from pyrigor.checkers import CHECKERS
from pyrigor.suppression import filter_suppressed
from pyrigor.violations import Violation

_DEFAULT_EXCLUDES = frozenset(
    {
        ".venv",
        "venv",
        ".git",
        "__pycache__",
        "node_modules",
        ".tox",
        "build",
        "dist",
        ".eggs",
        "site-packages",
    }
)


def _is_excluded(*, path: Path) -> bool:
    """Check whether any part of a path matches a default-excluded directory name.

    Args:
        path: The path to check.

    Returns:
        True if any path component matches a default exclude.
    """
    return any(part in _DEFAULT_EXCLUDES or part.endswith(".egg-info") for part in path.parts)


def _collect_python_files(*, paths: list[str]) -> list[str]:
    """Expand a mix of file and directory paths into a flat list of .py files.

    Args:
        paths: File or directory paths.

    Returns:
        Every .py file found — paths given directly, or discovered by
        recursively walking any directory paths, skipping excluded directories
        (.venv, .git, __pycache__, ...).
    """
    files: list[str] = []
    for path in paths:
        p = Path(path)
        if p.is_dir():
            files.extend(str(f) for f in p.rglob("*.py") if not _is_excluded(path=f))
        else:
            files.append(path)

    return files


def _read_source(*, path: str) -> str | None:
    """Read a file's source, handling decode/OS errors gracefully.

    Args:
        path: The file to read.

    Returns:
        The file's source text, or None if it couldn't be read.
    """
    try:
        return Path(path).read_text(encoding="utf-8-sig")
    except (UnicodeDecodeError, OSError) as error:
        print(f"Warning: skipping {path}: {error}", file=sys.stderr)
        return None


def _run_checkers(*, path: str, source: str) -> list[Violation]:
    """Run every registered checker against a source string, handling parse errors.

    Args:
        path: The file's path, for the warning message on failure.
        source: The file's source text.

    Returns:
        Every violation found, or an empty list if the source
        couldn't be parsed.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        print(f"Warning: skipping {path}: {error}", file=sys.stderr)
        return []

    return [v for checker in CHECKERS for v in checker(tree=tree)]


def _check_file(*, path: str) -> list[Violation]:
    """Check a single file and print any violations found.

    Args:
        path: The file to check.

    Returns:
        Every violation that is found in this file.
    """
    source = _read_source(path=path)
    if source is None:
        return []

    violations = _run_checkers(path=path, source=source)
    violations = filter_suppressed(violations=violations, source=source)

    for violation in violations:
        location = f"{path}:{violation.line}:{violation.column}"
        print(
            f"{location}: {violation.rule.name} Function '{violation.context_name}' "
            f"{violation.rule.problem} ({violation.rule.symbolic_name})"
        )

    return violations


def _format_rule_breakdown(*, violations: list[Violation]) -> str:
    """Build a per-rule violation count breakdown string.

    Args:
        violations: Every violation found across all files.

    Returns:
        A comma-separated "Rule: count" breakdown, for example, "PYR401: 2, PYR402: 5".
    """
    counts = Counter(v.rule.name for v in violations)
    return ", ".join(f"{rule}: {count}" for rule, count in sorted(counts.items()))


def _print_file_breakdown(*, violations_by_file: dict[str, list[Violation]]) -> None:
    """Print each file's own violation count, skipping clean files.

    Args:
        violations_by_file: Each checked file's own violations.
    """
    for path, file_violations in violations_by_file.items():
        if file_violations:
            print(f"{path}: {len(file_violations)}")


def _print_summary(
    *, files: list[str], elapsed: float, violations: list[Violation], violations_by_file: dict[str, list[Violation]]
) -> None:
    """Print the per-rule breakdown, per-file breakdown, and timing summary, in that order.

    Args:
        files: The files that were checked.
        elapsed: Elapsed time in seconds.
        violations: Every violation found across all files.
        violations_by_file: Each checked file's own violations.
    """
    if violations:
        print(_format_rule_breakdown(violations=violations))
        _print_file_breakdown(violations_by_file=violations_by_file)

    file_word = "file" if len(files) == 1 else "files"
    violation_word = "violation" if len(violations) == 1 else "violations"
    print(f"Checked {len(files)} {file_word} in {elapsed:.2f}s -- {len(violations)} {violation_word}")


def main(*, paths: list[str]) -> int:
    """Run all checkers against the given file paths.

    Args:
        paths: File or directory paths to check.

    Returns:
        0 if no violations were found, 1 otherwise.
    """
    files = _collect_python_files(paths=paths)
    start = time.perf_counter()

    violations_by_file = {path: _check_file(path=path) for path in files}
    all_violations = [v for file_violations in violations_by_file.values() for v in file_violations]
    exit_code = 1 if all_violations else 0

    elapsed = time.perf_counter() - start
    _print_summary(files=files, elapsed=elapsed, violations=all_violations, violations_by_file=violations_by_file)

    return exit_code


def run() -> None:
    """Console-script entry point: parse argv and run main()."""
    if "--version" in sys.argv:
        print(f"pyrigor {version('pyrigor')}")
        sys.exit(0)

    try:
        exit_code = main(paths=sys.argv[1:])
    except Exception as error:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        print(f"pyrigor crashed unexpectedly: {error}", file=sys.stderr)
        sys.exit(2)

    sys.exit(exit_code)


if __name__ == "__main__":  # pragma: no cover
    run()
