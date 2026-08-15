"""Command-line entry point for pyrigor's checkers."""

import ast
import sys
import time
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from typing import NamedTuple

from pyrigor.checkers import CHECKERS, RegisteredChecker
from pyrigor.rules import Rule
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


def _run_checkers(*, path: str, source: str, checkers: tuple[RegisteredChecker, ...]) -> list[Violation]:
    """Run every registered checker against a source string, handling parse errors.

    Args:
        path: The file's path, for the warning message on failure.
        source: The file's source text.
        checkers: The checkers to run.

    Returns:
        Every violation found, or an empty list if the source
        couldn't be parsed.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        print(f"Warning: skipping {path}: {error}", file=sys.stderr)
        return []

    return [v for entry in checkers for v in entry.find_violations(tree=tree)]


class FileCheckResult(NamedTuple):
    """A single file's checked violations, split by suppression."""

    kept: list[Violation]
    suppressed: list[Violation]


def _check_file(*, path: str, checkers: tuple[RegisteredChecker, ...]) -> FileCheckResult:
    """Check a single file and print any kept violations found.

    Args:
        path: The file to check.
        checkers: The checkers to run.

    Returns:
        The kept violations (printed) and the suppressed ones.
    """
    source = _read_source(path=path)
    if source is None:
        return FileCheckResult(kept=[], suppressed=[])

    violations = _run_checkers(path=path, source=source, checkers=checkers)
    result = filter_suppressed(violations=violations, source=source)

    for violation in result.kept:
        location = f"{path}:{violation.line}:{violation.column}"
        print(
            f"{location}: {violation.rule.name} Function '{violation.context_name}' "
            f"{violation.rule.problem} ({violation.rule.symbolic_name})"
        )

    return FileCheckResult(kept=result.kept, suppressed=result.suppressed)


def _format_rule_breakdown(*, violations: list[Violation]) -> str:
    """Build a per-rule violation count breakdown string.

    Args:
        violations: Every violation found across all files.

    Returns:
        A comma-separated "Rule: count" breakdown, for example, "PYR401: 2, PYR402: 5".
    """
    counts = Counter(v.rule.name for v in violations)
    return ", ".join(f"{rule}: {count}" for rule, count in sorted(counts.items()))


def _format_suppressed_breakdown(*, suppressed: list[Violation]) -> str:
    """Build a per-rule suppressed-violation count breakdown string.

    Args:
        suppressed: Every violation that was suppressed across all files.

    Returns:
        A comma-separated "Rule: count suppressed" breakdown.
    """
    counts = Counter(v.rule.name for v in suppressed)
    return ", ".join(f"{rule}: {count} suppressed" for rule, count in sorted(counts.items()))


def _print_file_breakdown(*, violations_by_file: dict[str, list[Violation]]) -> None:
    """Print each file's own violation count, skipping clean files.

    Args:
        violations_by_file: Each checked file's own violations.
    """
    for path, file_violations in violations_by_file.items():
        if file_violations:
            print(f"{path}: {len(file_violations)}")


def _print_summary(
    *,
    files: list[str],
    elapsed: float,
    violations: list[Violation],
    violations_by_file: dict[str, list[Violation]],
    suppressed: list[Violation],
) -> None:
    """Print the per-file breakdown, per-rule breakdown, suppression breakdown, and timing summary.

    Args:
        files: The files that were checked.
        elapsed: Elapsed time in seconds.
        violations: Every violation found across all files.
        violations_by_file: Each checked file's own violations.
        suppressed: Every violation that was suppressed across all files.
    """
    if violations:
        _print_file_breakdown(violations_by_file=violations_by_file)
        print(_format_rule_breakdown(violations=violations))

    if suppressed:
        print(_format_suppressed_breakdown(suppressed=suppressed))

    file_word = "file" if len(files) == 1 else "files"
    violation_word = "violation" if len(violations) == 1 else "violations"
    print(f"Checked {len(files)} {file_word} in {elapsed:.2f}s -- {len(violations)} {violation_word}")


class _CheckResults(NamedTuple):
    """Aggregated results across every checked file."""

    all_violations: list[Violation]
    all_suppressed: list[Violation]
    kept_by_file: dict[str, list[Violation]]


def _collect_all_violations(*, results_by_file: dict[str, FileCheckResult]) -> list[Violation]:
    """Flatten every file's kept violations into one list.

    Args:
        results_by_file: Each file's own kept and suppressed violations.

    Returns:
        Every kept violation across all files.
    """
    return [v for result in results_by_file.values() for v in result.kept]


def _collect_all_suppressed(*, results_by_file: dict[str, FileCheckResult]) -> list[Violation]:
    """Flatten every file's suppressed violations into one list.

    Args:
        results_by_file: Each file's own kept and suppressed violations.

    Returns:
        Every suppressed violation across all files.
    """
    return [v for result in results_by_file.values() for v in result.suppressed]


def _kept_by_file(*, results_by_file: dict[str, FileCheckResult]) -> dict[str, list[Violation]]:
    """Extract each file's kept violations, for the per-file breakdown.

    Args:
        results_by_file: Each file's own kept and suppressed violations.

    Returns:
        A path-to-kept-violations mapping.
    """
    return {path: result.kept for path, result in results_by_file.items()}


def _aggregate_results(*, results_by_file: dict[str, FileCheckResult]) -> _CheckResults:
    """Flatten per-file check results into overall totals.

    Args:
        results_by_file: Each file's own kept and suppressed violations.

    Returns:
        Every kept violation, every suppressed violation, and a
        path-to-kept-violations mapping for the per-file breakdown.
    """
    return _CheckResults(
        all_violations=_collect_all_violations(results_by_file=results_by_file),
        all_suppressed=_collect_all_suppressed(results_by_file=results_by_file),
        kept_by_file=_kept_by_file(results_by_file=results_by_file),
    )


def _matches_rule_filter(*, rule: Rule, only: set[str]) -> bool:
    """Check whether a rule matches a lenient --only filter set.

    Args:
        rule: The rule to check.
        only: Tokens from --only, each is a full code, bare number, or symbolic name.

    Returns:
        True if the rule's code, numeric shorthand, or symbolic name is in only.
    """
    code = rule.name
    shorthand = code.removeprefix("PYR")
    name = rule.symbolic_name

    return bool(only & {code, shorthand, name})


def _filter_checkers(*, only: set[str] | None) -> tuple[RegisteredChecker, ...]:
    """Filter CHECKERS down to only the rules matching --only if given.

    Args:
        only: Tokens from --only, or None to run every registered checker.

    Returns:
        The filtered checker tuple, or all the CHECKERS if only is None.
    """
    if only is None:
        return CHECKERS

    return tuple(entry for entry in CHECKERS if _matches_rule_filter(rule=entry.rule, only=only))


def main(*, paths: list[str], only: set[str] | None = None) -> int:
    """Run all checkers against the given file paths.

    Args:
        paths: File or directory paths to check.
        only: Rule codes/shorthand/symbolic names to restrict checking
            to, or None to run every registered checker.

    Returns:
        0 if no violations were found, 1 otherwise.
    """
    files = _collect_python_files(paths=paths)
    checkers = _filter_checkers(only=only)
    start = time.perf_counter()

    results_by_file = {path: _check_file(path=path, checkers=checkers) for path in files}
    results = _aggregate_results(results_by_file=results_by_file)
    exit_code = 1 if results.all_violations else 0

    elapsed = time.perf_counter() - start
    _print_summary(
        files=files,
        elapsed=elapsed,
        violations=results.all_violations,
        violations_by_file=results.kept_by_file,
        suppressed=results.all_suppressed,
    )

    return exit_code


def _extract_only_flag(*, args: list[str]) -> set[str] | None:
    """Find and remove a --only=CODE, CODE argument from args, if present.

    Args:
        args: The argv list to search (mutated in place if found).

    Returns:
        The parsed set of tokens, or None if no --only= flag was given.
    """
    for i, arg in enumerate(args):
        if arg.startswith("--only="):
            only = {token.strip() for token in arg.removeprefix("--only=").split(",")}
            del args[i]
            return only

    return None


def _known_rule_identities() -> set[str]:
    """Collect every valid way to refer to a registered rule: code, shorthand, symbolic name.

    Returns:
        The full set of tokens --only will accept.
    """
    codes = {entry.rule.name for entry in CHECKERS}
    shorthands = {entry.rule.name.removeprefix("PYR") for entry in CHECKERS}
    symbolic_names = {entry.rule.symbolic_name for entry in CHECKERS}

    return codes | shorthands | symbolic_names


def _validate_only_flag(*, only: set[str] | None) -> None:
    """Exit with an error if --only contains a code that matches no registered rule.

    Args:
        only: Tokens from --only, or None if the flag was not given.
    """
    if only is None:
        return

    unknown = only - _known_rule_identities()
    if unknown:
        print(f"pyrigor: unknown rule code(s) in --only: {', '.join(sorted(unknown))}", file=sys.stderr)
        sys.exit(2)


def run() -> None:
    """Console-script entry point: parse argv and run main()."""
    if "--version" in sys.argv:
        print(f"pyrigor {version('pyrigor')}")
        sys.exit(0)

    args = list(sys.argv[1:])
    only = _extract_only_flag(args=args)
    _validate_only_flag(only=only)

    try:
        exit_code = main(paths=args, only=only)
    except Exception as error:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        print(f"pyrigor crashed unexpectedly: {error}", file=sys.stderr)
        sys.exit(2)

    sys.exit(exit_code)


if __name__ == "__main__":  # pragma: no cover
    run()
