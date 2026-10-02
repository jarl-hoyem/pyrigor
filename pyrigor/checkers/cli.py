"""Command-line entry point for pyrigor's checkers."""

import argparse
import ast
import difflib
import json
import os
import sys
import time
import tokenize
import unicodedata
from collections import Counter
from importlib.metadata import version
from io import TextIOWrapper
from pathlib import Path
from typing import Final, Literal, NamedTuple, Never, cast

from pyrigor.checkers import CHECKERS, RegisteredChecker
from pyrigor.checkers._shared import walk_once
from pyrigor.diagnostics import (
    CheckError,
    DiagnosticInputError,
    DiagnosticsDocument,
    RuleMetadata,
    Summary,
    ToolMetadata,
    document_to_json,
    require_supported_findings,
)
from pyrigor.finding_builder import FindingContext
from pyrigor.findings import FileName, Finding, PositionIndex
from pyrigor.fixers.pyr402_keyword_only_arguments_fixer import FixRejectedError, FixResult, FixStatus, fix_source
from pyrigor.rules import Rule
from pyrigor.suppression import filter_suppressed

_MISSING_PATHS_MESSAGE: Final = "the following arguments are required: paths"
_EXIT_CODE_USAGE_ERROR: Final = 2

_DEFAULT_EXCLUDES: Final = frozenset(
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

OutputFormat = Literal["human", "json"]
_JSON_OUTPUT_FORMAT: Final = "json"
_MALFORMED_SUPPRESSION: Final = "malformed_suppression"


class _SourceOk(NamedTuple):
    """A file's source, read successfully."""

    source: str
    position_index: PositionIndex


class _SourceFailed(NamedTuple):
    """A file's source could not be read."""

    error: CheckError


_SourceResult = _SourceOk | _SourceFailed


class _FixSourceOk(NamedTuple):
    """A file's byte-preserving source, read successfully."""

    source: bytes


class _FixSourceFailed(NamedTuple):
    """A file's byte-preserving source could not be read."""

    error: CheckError


_FixSourceResult = _FixSourceOk | _FixSourceFailed


class _FixInput(NamedTuple):
    """A readable source and its prepared fixer result."""

    original: bytes
    prepared: FixResult


class _RunOptions(NamedTuple):
    """Validated options needed to execute the CLI."""

    paths: list[str]
    select: set[str] | None
    ignore: set[str] | None
    excludes: list[str] | None
    output_format: OutputFormat
    fix: bool
    diff: bool


class _CheckerResult(NamedTuple):
    """The parser/checker result and any associated file error."""

    findings: list[Finding]
    error: CheckError | None
    tokens: tuple[tokenize.TokenInfo, ...] | None = None


def _is_excluded(*, path: Path) -> bool:
    """Check whether any part of a path matches a default-excluded directory name.

    Args:
        path: The path to check.

    Returns:
        True if any path component matches a default exclude.
    """
    return any(part in _DEFAULT_EXCLUDES or part.endswith(".egg-info") for part in path.parts)


def _is_path_excluded(*, path: Path, excludes: tuple[Path, ...]) -> bool:
    """Check whether a path is within one of the user-excluded paths."""
    resolved = path.resolve()
    return any(resolved == excluded or excluded in resolved.parents for excluded in excludes)


def _files_in_directory(*, path: Path, excludes: tuple[Path, ...]) -> list[str]:
    """Recursively find every .py file in a directory, skipping excluded ones.

    Args:
        path: The directory to walk.
        excludes: Resolved files or directories to omit.

    Returns:
        Every non-excluded .py file found.
    """
    return [
        str(f)
        for f in path.rglob("*.py")
        if not _is_excluded(path=f) and not _is_path_excluded(path=f, excludes=excludes)
    ]


def _candidates_for_path(*, path: str, excludes: tuple[Path, ...]) -> list[str]:
    """Expand a single file or directory argument into its .py file candidates.

    Args:
        path: A file or directory path.
        excludes: Resolved files or directories to omit.

    Returns:
        [path] itself if it is a file, or every non-excluded .py file
        found by recursively walking it if it is a directory.
    """
    p = Path(path)
    return (
        _files_in_directory(path=p, excludes=excludes)
        if p.is_dir()
        else ([] if _is_path_excluded(path=p, excludes=excludes) else [path])
    )


def _collect_python_files(*, paths: list[str], excludes: list[str] | None = None) -> list[str]:
    """Expand a mix of file and directory paths into a flat list of distinct .py files.

    Args:
        paths: File or directory paths.
        excludes: Files or directories to omit, or None for no user exclusions.

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
    excluded_paths = tuple(Path(path).resolve() for path in (excludes or []))
    for path in paths:
        _append_unique_candidates(
            candidates=_candidates_for_path(path=path, excludes=excluded_paths),
            files=files,
            seen=seen,
        )

    return files


def _append_unique_candidates(*, candidates: list[str], files: list[str], seen: set[Path]) -> None:
    """Append candidates not already represented by a resolved path."""
    for candidate in candidates:
        resolved = Path(candidate).resolve()
        if resolved not in seen:
            seen.add(resolved)
            files.append(candidate)


def _file_sort_key(*, path: str) -> str:
    """Return a platform- and argument-order-independent sort key for a file path.

    Args:
        path: The file path to the key, in whatever form it was discovered or given.

    Returns:
        The path with forward slashes, compared by Unicode code point (plain Python string order), so the
        same set of files sorts identically regardless of the platform's path separator or discovery order.
    """
    # A plain string replace, not Path(path).as_posix(): pathlib only treats backslash as a separator on
    # Windows, so as_posix() leaves a backslash untouched when this runs on Linux or macOS, breaking the very
    # platform-independence this function exists to provide.
    return path.replace("\\", "/")


class _FindingSortKey(NamedTuple):
    """A deterministic ordering key for one finding within its file."""

    line: int
    column: int
    end_line: int
    end_column: int
    rule_code: str


def _finding_sort_key(*, finding: Finding) -> _FindingSortKey:
    """Order by the primary start, end and rule code, independent of registration."""
    primary = next(span for span in finding.spans if span.is_primary)
    return _FindingSortKey(
        line=primary.line_start,
        column=primary.column_start,
        end_line=primary.line_end,
        end_column=primary.column_end,
        rule_code=finding.code.name,
    )


def _file_name(*, path: str) -> FileName:
    """Return an NFC path relative to the working directory with forward slashes."""
    try:
        relative = Path(os.path.relpath(path)).as_posix()
    except ValueError as error:
        raise DiagnosticInputError(
            f"{path!r}: no path relative to the working directory exists; run from the file's drive"
        ) from error
    return FileName(unicodedata.normalize("NFC", relative))


def _read_source(*, path: str) -> _SourceResult:
    """Read and decode original source bytes, returning structured read errors."""
    try:
        return _decode_source(raw=Path(path).read_bytes())
    except (UnicodeDecodeError, OSError) as error:
        return _SourceFailed(error=CheckError(file_name=_file_name(path=path), kind="read_error", message=str(error)))


def _decode_source(*, raw: bytes) -> _SourceOk:
    """Decode the same bytes used by the position index with universal newlines."""
    source = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    return _SourceOk(source=source, position_index=PositionIndex(raw=raw))


def _read_fix_source(*, path: str) -> _FixSourceResult:
    """Read fixer input as bytes so BOMs and line endings can be preserved."""
    try:
        return _FixSourceOk(source=Path(path).read_bytes())
    except OSError as error:
        return _FixSourceFailed(
            error=CheckError(file_name=_file_name(path=path), kind="read_error", message=str(error))
        )


def _syntax_column(*, error: SyntaxError) -> int | None:
    """Retain only positive parser columns in the diagnostics document."""
    return error.offset if error.offset is not None and error.offset > 0 else None


def _run_checkers(
    *, path: str, source: str, index: PositionIndex, checkers: tuple[RegisteredChecker, ...]
) -> _CheckerResult:
    """Run selected checkers on shared source positions, returning structured parse errors."""
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return _CheckerResult(
            findings=[],
            error=CheckError(
                file_name=_file_name(path=path),
                kind="parse_error",
                message=str(error),
                line=error.lineno,
                column=_syntax_column(error=error),
            ),
        )

    nodes = walk_once(tree=tree)
    context = FindingContext(source=source, index=index, file_name=_file_name(path=path), parents=nodes.parents)
    findings = [finding for entry in checkers for finding in entry.find_findings(nodes=nodes, context=context)]
    require_supported_findings(findings=findings, path=path)
    return _CheckerResult(
        findings=findings,
        error=None,
        tokens=context.tokens if findings else None,
    )


class FileCheckResult(NamedTuple):
    """A single file's checked findings, split by suppression."""

    kept: list[Finding]
    suppressed: list[Finding]
    errors: list[CheckError]


def _check_file(*, path: str, checkers: tuple[RegisteredChecker, ...]) -> FileCheckResult:
    """Build canonical findings and partition them by primary-span suppression comments."""
    source_result = _read_source(path=path)
    if isinstance(source_result, _SourceFailed):
        return FileCheckResult(
            kept=[],
            suppressed=[],
            errors=[source_result.error],
        )

    checker_result = _run_checkers(
        path=path, source=source_result.source, index=source_result.position_index, checkers=checkers
    )
    if checker_result.error is not None:
        return FileCheckResult(
            kept=[],
            suppressed=[],
            errors=[checker_result.error],
        )

    result = filter_suppressed(
        findings=checker_result.findings, source=source_result.source, tokens=checker_result.tokens
    )
    return FileCheckResult(
        kept=sorted(result.kept, key=lambda finding: _finding_sort_key(finding=finding)),
        suppressed=sorted(result.suppressed, key=lambda finding: _finding_sort_key(finding=finding)),
        errors=list(result.errors),
    )


def _rule_count_breakdown(*, findings: list[Finding], suffix: str = "") -> str:
    """Build a per-rule finding count breakdown string, optionally suffixed.

    Args:
        findings: Findings to count, grouped by rule.
        suffix: Text appended after each count (for example, "suppressed"), or "" for none.

    Returns:
        A comma-separated "Rule: count[suffix]" breakdown, sorted by rule name.
    """
    counts = Counter(v.code.name for v in findings)
    return ", ".join(f"{rule}: {count}{suffix}" for rule, count in sorted(counts.items()))


def _format_rule_breakdown(*, findings: list[Finding]) -> str:
    """Build a per-rule finding count breakdown string.

    Args:
        findings: Every finding that is found across all files.

    Returns:
        A comma-separated "Rule: count" breakdown, for example, "PYR401: 2, PYR402: 5".
    """
    return _rule_count_breakdown(findings=findings)


def _format_suppressed_breakdown(*, suppressed: list[Finding]) -> str:
    """Build a per-rule suppressed-finding count breakdown string.

    Args:
        suppressed: Every finding that was suppressed across all files.

    Returns:
        A comma-separated "Rule: count suppressed" breakdown.
    """
    return _rule_count_breakdown(findings=suppressed, suffix=" suppressed")


def _print_file_breakdown(*, findings_by_file: dict[str, list[Finding]]) -> None:
    """Print each file's own finding count, skipping clean files.

    Args:
        findings_by_file: Each checked file's own findings.
    """
    for path, file_findings in findings_by_file.items():
        if file_findings:
            print(f"{path}: {len(file_findings)}")


def _print_summary(
    *,
    files: list[str],
    elapsed: float,
    findings: list[Finding],
    findings_by_file: dict[str, list[Finding]],
    suppressed: list[Finding],
) -> None:
    """Print the per-file breakdown, per-rule breakdown, suppression breakdown and timing summary.

    Args:
        files: The files that were checked.
        elapsed: Elapsed time in seconds.
        findings: Every finding that is found across all files.
        findings_by_file: Each checked file's own findings.
        suppressed: The suppressed findings from every file.
    """
    if findings:
        _print_file_breakdown(findings_by_file=findings_by_file)
        print(_format_rule_breakdown(findings=findings))

    if suppressed:
        print(_format_suppressed_breakdown(suppressed=suppressed))

    file_word = "file" if len(files) == 1 else "files"
    finding_word = "finding" if len(findings) == 1 else "findings"
    print(f"Checked {len(files)} {file_word} in {elapsed:.2f}s -- {len(findings)} {finding_word}")


def _print_human_results(*, results_by_file: dict[str, FileCheckResult]) -> None:
    """Print file warnings and diagnostics in the existing human format."""
    for path, result in results_by_file.items():
        for error in result.errors:
            _print_error(path=path, error=error)
        for finding in result.kept:
            _print_finding(path=path, finding=finding)


def _print_finding(*, path: str, finding: Finding) -> None:
    """Render one finding at its primary span in the human format."""
    primary = next(span for span in finding.spans if span.is_primary)
    location = f"{path}:{primary.line_start}:{primary.column_start}"
    print(f"{location}: {finding.code.name} {finding.message} ({finding.code.symbolic_name})")


def _print_error(*, path: str, error: CheckError) -> None:
    """Report malformed comments as warnings and unreadable source as skipped files."""
    if error.kind == _MALFORMED_SUPPRESSION:
        print(f"Warning: {error.message}", file=sys.stderr)
    else:
        print(f"Warning: skipping {path}: {error.message}", file=sys.stderr)


def _selected_rules(*, checkers: tuple[RegisteredChecker, ...], release: str) -> dict[Rule, RuleMetadata]:
    """Include every selected rule with a guideline URL pinned to the producing release."""
    return {
        entry.rule: RuleMetadata(
            symbolic_name=entry.rule.symbolic_name,
            fix_availability=entry.rule.fix_availability,
            applicability=entry.rule.applicability,
            url=f"https://github.com/jarl-hoyem/pyrigor/blob/v{release}/guidelines/"
            f"{entry.rule.name}-{entry.rule.symbolic_name}.md",
        )
        for entry in sorted(checkers, key=lambda entry: entry.rule.name)
    }


def _print_json_results(
    *,
    files: list[str],
    results_by_file: dict[str, FileCheckResult],
    results: "_CheckResults",
    checkers: tuple[RegisteredChecker, ...],
) -> None:
    """Print one complete v2 document, leaving operational warnings on stderr."""
    for path, result in results_by_file.items():
        for error in result.errors:
            _print_error(path=path, error=error)
    release = version("pyrigor")
    document = DiagnosticsDocument(
        tool=ToolMetadata(name="pyrigor", version=release),
        findings=results.all_findings,
        suppressed=results.all_suppressed,
        rules=_selected_rules(checkers=checkers, release=release),
        errors=results.errors,
        summary=Summary(files_checked=len(files)),
    )
    print(json.dumps(document_to_json(document=document), ensure_ascii=False, indent=2))


class _CheckResults(NamedTuple):
    """Aggregated results across every checked file."""

    all_findings: list[Finding]
    all_suppressed: list[Finding]
    kept_by_file: dict[str, list[Finding]]
    errors: list[CheckError]


def _collect_all_findings(*, results_by_file: dict[str, FileCheckResult]) -> list[Finding]:
    """Flatten every file's kept findings into one list.

    Args:
        results_by_file: Each file's own kept and suppressed findings.

    Returns:
        Every kept finding across all files.
    """
    return [finding for result in results_by_file.values() for finding in result.kept]


def _collect_all_suppressed(*, results_by_file: dict[str, FileCheckResult]) -> list[Finding]:
    """Flatten every file's suppressed findings into one list.

    Args:
        results_by_file: Each file's own kept and suppressed findings.

    Returns:
        Every suppressed finding across all files.
    """
    return [finding for result in results_by_file.values() for finding in result.suppressed]


def _kept_by_file(*, results_by_file: dict[str, FileCheckResult]) -> dict[str, list[Finding]]:
    """Extract each file's kept findings, for the per-file breakdown.

    Args:
        results_by_file: Each file's own kept and suppressed findings.

    Returns:
        A path-to-kept-findings mapping.
    """
    return {path: result.kept for path, result in results_by_file.items()}


def _collect_errors(*, results_by_file: dict[str, FileCheckResult]) -> list[CheckError]:
    """Flatten every file error into one list."""
    return sorted(
        (error for result in results_by_file.values() for error in result.errors),
        key=lambda error: (error.file_name, error.line or 0),
    )


def _aggregate_results(*, results_by_file: dict[str, FileCheckResult]) -> _CheckResults:
    """Flatten per-file check results into overall totals.

    Args:
        results_by_file: Each file's own kept and suppressed findings.

    Returns:
        Every kept finding, every suppressed finding and a
        path-to-kept-findings mapping for the per-file breakdown.
    """
    return _CheckResults(
        all_findings=_collect_all_findings(results_by_file=results_by_file),
        all_suppressed=_collect_all_suppressed(results_by_file=results_by_file),
        kept_by_file=_kept_by_file(results_by_file=results_by_file),
        errors=_collect_errors(results_by_file=results_by_file),
    )


def _matches_rule_filter(*, rule: Rule, tokens: set[str]) -> bool:
    """Check whether a rule matches a lenient token filter set.

    Args:
        rule: The rule to check.
        tokens: Tokens to match against, each is a full code, bare number or symbolic name.

    Returns:
        True if the rule's code, numeric shorthand or symbolic name is in tokens.
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


def main(
    *,
    paths: list[str],
    select: set[str] | None = None,
    ignore: set[str] | None = None,
    output_format: OutputFormat = "human",
    excludes: list[str] | None = None,
) -> int:
    """Run all checkers against the given file paths.

    Args:
        paths: File or directory paths to check.
        excludes: Files or directories to omit, or None for no user exclusions.
        select: Rule codes/shorthand/symbolic names to restrict checking
            to, or None to start from every registered checker.
        ignore: Rule codes/shorthand/symbolic names to exclude from
            checking, or None to exclude nothing.
        output_format: The output format, either human or JSON.

    Returns:
        0 if no findings were found, 1 otherwise.
    """
    files = sorted(
        _collect_python_files(paths=paths, excludes=excludes),
        key=lambda path: _file_sort_key(path=_file_name(path=path)),
    )
    checkers = _filter_checkers(select=select, ignore=ignore)
    start = time.perf_counter()

    results_by_file = {path: _check_file(path=path, checkers=checkers) for path in files}
    results = _aggregate_results(results_by_file=results_by_file)
    exit_code = 1 if results.all_findings else 0

    elapsed = time.perf_counter() - start
    if output_format == _JSON_OUTPUT_FORMAT:
        _print_json_results(files=files, results_by_file=results_by_file, results=results, checkers=checkers)
    else:
        _print_human_results(results_by_file=results_by_file)
        _print_summary(
            files=files,
            elapsed=elapsed,
            findings=results.all_findings,
            findings_by_file=results.kept_by_file,
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
        A parser recognising --version/-V, --select, --ignore, --output-format and paths.
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
    parser.add_argument(
        "--output-format",
        action="append",
        choices=("human", "json"),
        help="Output format (default: human).",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        metavar="PATH",
        help="Exclude this file or directory (and its contents), comma-separated; may be repeated.",
    )
    parser.add_argument("--fix", action="store_true", help="Apply safe fixes for the explicitly selected rules.")
    parser.add_argument("--diff", action="store_true", help="Show safe fixes as a unified diff without writing.")
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


def _parse_exclude_flags(*, values: list[str] | None) -> list[str] | None:
    """Split --exclude flags' comma-separated values into a flat list of paths.

    Unlike --select/--ignore (single flag, comma-separated), --exclude
    permits repetition. Each invocation can now be comma-separated, and all
    results flatten into one list.

    Args:
        values: The raw values argparse's append action collected for --exclude.

    Returns:
        A flat list of paths (each stripped of whitespace), or None if the flag was not given.
    """
    if not values:
        return None
    result: list[str] = []
    for value in values:
        result.extend(token.strip() for token in value.split(","))
    return result


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


def _validate_fix_selection(*, fix: bool, diff: bool, select: set[str] | None, output_format: OutputFormat) -> None:
    """Require explicit PYR402 selection for fixer modes."""
    if (fix or diff) and output_format == _JSON_OUTPUT_FORMAT:
        print("pyrigor: fixer options cannot be combined with --output-format json", file=sys.stderr)
        sys.exit(_EXIT_CODE_USAGE_ERROR)
    _validate_fixer_selection(fix=fix, diff=diff, select=select)


def _validate_fixer_selection(*, fix: bool, diff: bool, select: set[str] | None) -> None:
    """Require explicit PYR402 selection for fix and diff modes."""
    if (fix or diff) and not (select and _matches_rule_filter(rule=Rule.PYR402, tokens=select)):
        print("pyrigor: fixer options require explicit --select=PYR402", file=sys.stderr)
        sys.exit(_EXIT_CODE_USAGE_ERROR)


def _run_fixes(*, paths: list[str], excludes: list[str] | None, diff: bool) -> int:
    """Apply or preview the selected safe fixes."""
    for path in _collect_python_files(paths=paths, excludes=excludes):
        _fix_path(path=path, diff=diff)
    return 0


def _fix_path(*, path: str, diff: bool) -> None:
    """Apply or preview a fix for one path."""
    fix_input = _read_and_prepare_fix(path=path)
    if fix_input is None:
        return
    original, result = fix_input
    if result.status is FixStatus.UNCHANGED:
        return
    if diff:
        _print_fix_diff(path=path, original=original, fixed=cast("bytes", result.source))
        return
    Path(path).write_bytes(cast("bytes", result.source))
    print(f"Fixed {path}")


def _read_and_prepare_fix(*, path: str) -> _FixInput | None:
    """Read one file and prepare its safe fix, reporting rejected inputs."""
    source_result = _read_fix_source(path=path)
    if isinstance(source_result, _FixSourceFailed):
        print(f"{path}: {source_result.error.message}", file=sys.stderr)
        return None
    try:
        prepared = fix_source(source=source_result.source)
    except (FixRejectedError, UnicodeDecodeError) as error:
        print(f"{path}: fix rejected: {error}", file=sys.stderr)
        return None
    return _FixInput(original=source_result.source, prepared=prepared)


def _print_fix_diff(*, path: str, original: bytes, fixed: bytes) -> None:
    """Print a unified diff for one byte-preserving source fix."""
    print(
        "".join(
            difflib.unified_diff(
                original.decode("utf-8-sig").splitlines(keepends=True),
                fixed.decode("utf-8-sig").splitlines(keepends=True),
                fromfile=path,
                tofile=path,
            )
        ),
        end="",
    )


def _configure_output(*, output_format: OutputFormat) -> None:
    """Ensure a real JSON output stream writes UTF-8, leaving text captures alone."""
    if output_format != _JSON_OUTPUT_FORMAT:
        return
    stdout = sys.stdout
    # JSON retains Unicode characters, so a redirected stream must not inherit a legacy Windows encoding.
    if isinstance(stdout, TextIOWrapper):
        stdout.reconfigure(encoding="utf-8")


def run() -> None:
    """Console-script entry point: parse argv and run main()."""
    parser = _build_parser()
    options = _parse_run_options(args=parser.parse_args())

    if options.fix or options.diff:
        sys.exit(_run_fixes(paths=options.paths, excludes=options.excludes, diff=options.diff))

    _configure_output(output_format=options.output_format)

    try:
        exit_code = _run_diagnostics(options=options)
    except Exception as error:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        print(f"pyrigor crashed unexpectedly: {error}", file=sys.stderr)
        sys.exit(_EXIT_CODE_USAGE_ERROR)
    else:
        sys.exit(exit_code)


def _run_diagnostics(*, options: _RunOptions) -> int:
    """Report known producer limitations as clear usage errors before emitting any output."""
    try:
        return main(
            paths=options.paths,
            select=options.select,
            ignore=options.ignore,
            output_format=options.output_format,
            excludes=options.excludes,
        )
    except DiagnosticInputError as error:
        print(f"pyrigor: {error}", file=sys.stderr)
        return _EXIT_CODE_USAGE_ERROR


def _parse_run_options(*, args: argparse.Namespace) -> _RunOptions:
    """Parse and validate the namespace produced by the CLI parser."""
    _reject_repeated_flag(flag_name="--select", values=args.select)
    _reject_repeated_flag(flag_name="--ignore", values=args.ignore)
    _reject_repeated_flag(flag_name="--output-format", values=args.output_format)
    select = _parse_flag_tokens(values=args.select)
    ignore = _parse_flag_tokens(values=args.ignore)
    _validate_flag_tokens(flag_name="--select", tokens=select)
    _validate_flag_tokens(flag_name="--ignore", tokens=ignore)
    _reject_empty_selection(checkers=_filter_checkers(select=select, ignore=ignore))
    output_format: OutputFormat = args.output_format[0] if args.output_format else "human"
    _validate_fix_selection(fix=args.fix, diff=args.diff, select=select, output_format=output_format)
    return _RunOptions(
        paths=args.paths,
        select=select,
        ignore=ignore,
        excludes=_parse_exclude_flags(values=args.exclude),
        output_format=output_format,
        fix=args.fix,
        diff=args.diff,
    )


if __name__ == "__main__":  # pragma: no cover
    run()
