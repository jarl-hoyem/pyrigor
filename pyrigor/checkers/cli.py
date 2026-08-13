"""Command-line entry point for pyrigor's checkers."""

import sys
import time
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
        return [v for checker in CHECKERS for v in checker(source)]
    except SyntaxError as error:
        print(f"Warning: skipping {path}: {error}", file=sys.stderr)
        return []


def _check_file(*, path: str) -> bool:
    """Check a single file and print any violations found.

    Args:
        path: The file to check.

    Returns:
        True if any violation was printed (that is this file should
        contribute to a non-zero exit code).
    """
    source = _read_source(path=path)
    if source is None:
        return False

    violations = _run_checkers(path=path, source=source)
    violations = filter_suppressed(violations=violations, source=source)

    for violation in violations:
        location = f"{path}:{violation.line}:{violation.column}"
        print(
            f"{location}: {violation.rule.name} Function '{violation.function_name}' "
            f"{violation.rule.problem} ({violation.rule.symbolic_name})"
        )

    return bool(violations)


def main(paths: list[str]) -> int:
    """Run all checkers against the given file paths.

    Args:
        paths: File or directory paths to check.

    Returns:
        0 if no violations were found, 1 otherwise.
    """
    files = _collect_python_files(paths=paths)
    start = time.perf_counter()

    # A list, not a generator: any() must not short-circuit here, since every
    # file needs to run through _check_file() and print its violations, not
    # just the first one returning True.
    violated_files = [_check_file(path=path) for path in files]  # pylint: disable=use-a-generator
    exit_code = 1 if any(violated_files) else 0

    elapsed = time.perf_counter() - start
    file_word = "file" if len(files) == 1 else "files"
    print(f"Checked {len(files)} {file_word} in {elapsed:.2f}s")

    return exit_code


def run() -> None:
    """Console-script entry point: parse argv and run main()."""
    sys.exit(main(paths=sys.argv[1:]))


if __name__ == "__main__":  # pragma: no cover
    run()
