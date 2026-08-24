"""Command-line entry point for pyrigor's checkers."""

import argparse
import ast
import sys
import time
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from typing import Final, NamedTuple, Never

from pyrigor.checkers import CHECKERS, RegisteredChecker
from pyrigor.checkers._shared import walk_once
from pyrigor.rules import Rule
from pyrigor.suppression import filter_suppressed
from pyrigor.violations import KeptViolations, SuppressedViolations, Violation

_MISSING_PATHS_MESSAGE = "the following arguments are required: paths"
_EXIT_CODE_USAGE_ERROR: Final = 2

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
    },
)


def _is_excluded(*, path: Path) -> bool:
    """Check whether any part of a path matches a default-excluded directory name.

    Args:
        path: The path to check.

    Returns:
        True if any path component matches a default exclude.
    """
    return any(part in _DEFAULT_EXCLUDES or part.endswith(".egg-info") for part in path.parts)


def _files_in_directory(*, path: Path) -> list[str]:
    """Recursively find every .py file in a directory, skipping excluded ones.

    Args:
        path: The directory to walk.

    Returns:
        Every non-excluded .py file found.
    """
    return [str(f) for f in path.rglob("*.py") if not _is_excluded(path=f)]


def _candidates_for_path(*, path: str) -> list[str]:
    """Expand a single file or directory argument into its .py file candidates.

    Args:
        path: A file or directory path.

    Returns:
        [path] itself if it is a file, or every non-excluded .py file
        found by recursively walking it if it is a directory.
    """
    p = Path(path)
    return _files_in_directory(path=p) if p.is_dir() else [path]


def _collect_python_files(*, paths: list[str]) -> list[str]:
    """Expand a mix of file and directory paths into a flat list of distinct .py files.

    Args:
        paths: File or directory paths.

    Returns:
        Every distinct .py file found — paths given directly, or
        discovered by recursively walking any directory paths,
        skipping excluded directories (.venv, .git, __pycache__,
        ...). The same file reached via two different path strings
        (an overlapping directory argument, a relative versus absolute
        form) is checked only once, keeping its first-seen form.
    """
    files: list[str] = []
    seen: set[Path] = set()
    for path in paths:
        for candidate in _candidates_for_path(path=path):
            resolved = Path(candidate).resolve()
            if resolved not in seen:
                seen.add(resolved)
                files.append(candidate)

    return files


def _read_source(*, path: str) -> str | None:
    """Read a file's source, handling decode/OS errors gracefully.

    Args:
        path: The file to read.

    Returns:
        The file's source text, or None if it could not be read.
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
        could not be parsed.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        print(f"Warning: skipping {path}: {error}", file=sys.stderr)
        return []

    nodes = walk_once(tree=tree)
    return [v for entry in checkers for v in entry.find_violations(nodes=nodes)]


class FileCheckResult(NamedTuple):
    """A single file's checked violations, split by suppression."""

    kept: KeptViolations
    suppressed: SuppressedViolations


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
        return FileCheckResult(kept=KeptViolations([]), suppressed=SuppressedViolations([]))

    violations = _run_checkers(path=path, source=source, checkers=checkers)
    result = filter_suppressed(violations=violations, source=source)

    for violation in result.kept:
        location = f"{path}:{violation.line}:{violation.column}"
        print(
            f"{location}: {violation.rule.name} {violation.context_kind} '{violation.context_name}' "
            f"{violation.rule.problem} ({violation.rule.symbolic_name})",
        )

    return FileCheckResult(kept=result.kept, suppressed=result.suppressed)


def _rule_count_breakdown(*, violations: list[Violation], suffix: str = "") -> str:
    """Build a per-rule violation count breakdown string, optionally suffixed.

    Args:
        violations: Violations to count, grouped by rule.
        suffix: Text appended after each count (for example, " suppressed"), or "" for none.

    Returns:
        A comma-separated "Rule: count[suffix]" breakdown, sorted by rule name.
    """
    counts = Counter(v.rule.name for v in violations)
    return ", ".join(f"{rule}: {count}{suffix}" for rule, count in sorted(counts.items()))


def _format_rule_breakdown(*, violations: KeptViolations) -> str:
    """Build a per-rule violation count breakdown string.

    Args:
        violations: Every violation found across all files.

    Returns:
        A comma-separated "Rule: count" breakdown, for example, "PYR401: 2, PYR402: 5".
    """
    return _rule_count_breakdown(violations=violations)


def _format_suppressed_breakdown(*, suppressed: SuppressedViolations) -> str:
    """Build a per-rule suppressed-violation count breakdown string.

    Args:
        suppressed: Every violation that was suppressed across all files.

    Returns:
        A comma-separated "Rule: count suppressed" breakdown.
    """
    return _rule_count_breakdown(violations=suppressed, suffix=" suppressed")


def _print_file_breakdown(*, violations_by_file: dict[str, KeptViolations]) -> None:
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
    violations: KeptViolations,
    violations_by_file: dict[str, KeptViolations],
    suppressed: SuppressedViolations,
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

    all_violations: KeptViolations
    all_suppressed: SuppressedViolations
    kept_by_file: dict[str, KeptViolations]


def _collect_all_violations(*, results_by_file: dict[str, FileCheckResult]) -> KeptViolations:
    """Flatten every file's kept violations into one list.

    Args:
        results_by_file: Each file's own kept and suppressed violations.

    Returns:
        Every kept violation across all files.
    """
    return KeptViolations([v for result in results_by_file.values() for v in result.kept])


def _collect_all_suppressed(*, results_by_file: dict[str, FileCheckResult]) -> SuppressedViolations:
    """Flatten every file's suppressed violations into one list.

    Args:
        results_by_file: Each file's own kept and suppressed violations.

    Returns:
        Every suppressed violation across all files.
    """
    return SuppressedViolations([v for result in results_by_file.values() for v in result.suppressed])


def _kept_by_file(*, results_by_file: dict[str, FileCheckResult]) -> dict[str, KeptViolations]:
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


def _matches_rule_filter(*, rule: Rule, tokens: set[str]) -> bool:
    """Check whether a rule matches a lenient token filter set.

    Args:
        rule: The rule to check.
        tokens: Tokens to match against, each is a full code, bare number, or symbolic name.

    Returns:
        True if the rule's code, numeric shorthand, or symbolic name is in tokens.
    """
    code = rule.name
    shorthand = code.removeprefix("PYR")
    name = rule.symbolic_name

    return bool(tokens & {code, shorthand, name})


def _apply_select(*, checkers: tuple[RegisteredChecker, ...], select: set[str] | None) -> tuple[RegisteredChecker, ...]:
    """Narrow checkers down to '--select's' set, or leave them unchanged if select is None.

    Args:
        checkers: The checkers to narrow.
        select: Tokens from --select, or None to leave checkers unchanged.

    Returns:
        The narrowed checker tuple.
    """
    if select is None:
        return checkers
    return tuple(entry for entry in checkers if _matches_rule_filter(rule=entry.rule, tokens=select))


def _apply_ignore(*, checkers: tuple[RegisteredChecker, ...], ignore: set[str] | None) -> tuple[RegisteredChecker, ...]:
    """Remove '--ignore's' set from checkers, or leave them unchanged if ignore is None.

    Args:
        checkers: The checkers to filter.
        ignore: Tokens from --ignore, or None to leave checkers unchanged.

    Returns:
        The filtered checker tuple.
    """
    if ignore is None:
        return checkers
    return tuple(entry for entry in checkers if not _matches_rule_filter(rule=entry.rule, tokens=ignore))


def _filter_checkers(*, select: set[str] | None, ignore: set[str] | None) -> tuple[RegisteredChecker, ...]:
    """Filter CHECKERS down to the rules matching --select, minus --ignore.

    Args:
        select: Tokens from --select, or None to start from every registered checker.
        ignore: Tokens from --ignore, or None to exclude nothing.

    Returns:
        The filtered checker tuple.
    """
    selected = _apply_select(checkers=CHECKERS, select=select)
    return _apply_ignore(checkers=selected, ignore=ignore)


def main(*, paths: list[str], select: set[str] | None = None, ignore: set[str] | None = None) -> int:
    """Run all checkers against the given file paths.

    Args:
        paths: File or directory paths to check.
        select: Rule codes/shorthand/symbolic names to restrict checking
            to, or None to start from every registered checker.
        ignore: Rule codes/shorthand/symbolic names to exclude from
            checking, or None to exclude nothing.

    Returns:
        0 if no violations were found, 1 otherwise.
    """
    files = _collect_python_files(paths=paths)
    checkers = _filter_checkers(select=select, ignore=ignore)
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


def _print_swallowed_path_hint() -> None:
    """Print a hint if the --select/--ignore space-separated form likely consumed the intended path."""
    argv = sys.argv[1:]
    for index, arg in enumerate(argv[:-1]):
        if arg in {"--select", "--ignore"}:
            print(
                f"pyrigor: hint: '{argv[index + 1]}' was consumed as {arg}'s value, leaving no path "
                f"argument. If {arg} was meant to filter by rule, give it a real code (e.g. "
                f"{arg}=PYR401) and provide the path separately. Otherwise, remove {arg}.",
                file=sys.stderr,
            )
            return


class _PyrigorArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that hints when --select/--ignore likely swallowed the path argument."""

    # pyrigor 403 # overrides argparse.ArgumentParser.error()'s fixed positional signature
    def error(self, message: str) -> Never:
        """Print a hint before the default error if --select/--ignore likely ate a path.

        Args:
            message: argparse's own error message.
        """
        if message == _MISSING_PATHS_MESSAGE:
            _print_swallowed_path_hint()
        super().error(message)


def _build_parser() -> argparse.ArgumentParser:
    """Build the console-script's argument parser.

    Returns:
        A parser recognizing --version/-V, --select, --ignore, and one or more paths.
    """
    parser = _PyrigorArgumentParser(prog="pyrigor", allow_abbrev=False)
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"pyrigor {version('pyrigor')}",
    )
    parser.add_argument(
        "--select",
        # action="append", not the default, so a second '--select' can be detected and rejected below
        action="append",
        help=(
            "Restrict checking to these rule codes, comma-separated (full code, bare number, "
            "or symbolic name: for example, PYR402, 402, or keyword-only-arguments)."
        ),
    )
    parser.add_argument(
        "--ignore",
        # action="append", not the default, so a second '--ignore' can be detected and rejected below
        action="append",
        help=(
            "Exclude these rule codes from checking, comma-separated (full code, bare number, "
            "or symbolic name: for example, PYR402, 402, or keyword-only-arguments)."
        ),
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to check.")
    return parser


def _reject_repeated_flag(*, flag_name: str, values: list[str] | None) -> None:
    """Exit with an error if a flag accepting one value was given more than once.

    Args:
        flag_name: The flag's name, for the error message (for example, "--select").
        values: The raw values argparse's append action is collected.
    """
    if values is not None and len(values) > 1:
        print(
            f"pyrigor: {flag_name} can only be given once (use {flag_name}=CODE,CODE for multiple rules)",
            file=sys.stderr,
        )
        sys.exit(_EXIT_CODE_USAGE_ERROR)


def _parse_flag_tokens(*, values: list[str] | None) -> set[str] | None:
    """Split a flag's single collected value into its comma-separated tokens.

    Args:
        values: The raw values argparse's append action collected, already
            confirmed by _reject_repeated_flag to contain at most one entry.

    Returns:
        The parsed set of tokens, or None if the flag was not given.
    """
    if not values:
        return None
    return {token.strip() for token in values[0].split(",")}


def _known_rule_identities() -> set[str]:
    """Collect every valid way to refer to a registered rule: code, shorthand, symbolic name.

    Returns:
        The full set of tokens --select/--ignore will accept.
    """
    codes = {entry.rule.name for entry in CHECKERS}
    shorthands = {entry.rule.name.removeprefix("PYR") for entry in CHECKERS}
    symbolic_names = {entry.rule.symbolic_name for entry in CHECKERS}

    return codes | shorthands | symbolic_names


def _validate_flag_tokens(*, flag_name: str, tokens: set[str] | None) -> None:
    """Exit with an error if tokens contain a code that matches no registered rule.

    Args:
        flag_name: The flag's name, for the error message (for example, "--select").
        tokens: Tokens from the flag, or None if the flag was not given.
    """
    if tokens is None:
        return

    unknown = tokens - _known_rule_identities()
    if unknown:
        print(f"pyrigor: unknown rule code(s) in {flag_name}: {', '.join(sorted(unknown))}", file=sys.stderr)
        sys.exit(_EXIT_CODE_USAGE_ERROR)


def _reject_empty_selection(*, checkers: tuple[RegisteredChecker, ...]) -> None:
    """Exit with an error if --select/--ignore combines to leave no rules to check.

    Args:
        checkers: The checkers --select/--ignore filtered down to.
    """
    if not checkers:
        print("pyrigor: --select and --ignore combine to leave no rules to check", file=sys.stderr)
        sys.exit(_EXIT_CODE_USAGE_ERROR)


def run() -> None:
    """Console-script entry point: parse argv and run main()."""
    parser = _build_parser()
    args = parser.parse_args()

    _reject_repeated_flag(flag_name="--select", values=args.select)
    _reject_repeated_flag(flag_name="--ignore", values=args.ignore)
    select = _parse_flag_tokens(values=args.select)
    ignore = _parse_flag_tokens(values=args.ignore)
    _validate_flag_tokens(flag_name="--select", tokens=select)
    _validate_flag_tokens(flag_name="--ignore", tokens=ignore)
    _reject_empty_selection(checkers=_filter_checkers(select=select, ignore=ignore))

    try:
        exit_code = main(paths=args.paths, select=select, ignore=ignore)
    except Exception as error:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        print(f"pyrigor crashed unexpectedly: {error}", file=sys.stderr)
        sys.exit(_EXIT_CODE_USAGE_ERROR)

    sys.exit(exit_code)


if __name__ == "__main__":  # pragma: no cover
    run()
