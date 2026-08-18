"""Suppression-comment mechanism for pyrigor's checkers.

Recognizes `# pyrigor: CODE[, CODE...]` comments on the same line as a
violation, on the line directly above it, or anywhere within a
multi-line statement's own span. CODE may be a rule's full code
("PYR402"), its numeric shorthand ("402"), or its symbolic name
("keyword-only-arguments"). Whitespace around the colon and commas is
tolerated.
"""

import re
import sys
from typing import NamedTuple

from pyrigor.violations import Violation


class _SuppressionInfo(NamedTuple):
    """Parsed contents of a `# pyrigor:` suppression comment."""

    tokens: set[str]
    reason: str | None


class SuppressionResult(NamedTuple):
    """The result of filtering violations by suppression comments."""

    kept: list[Violation]
    suppressed: list[Violation]


_SUPPRESSION_PATTERN = re.compile(r"#\s*pyrigor\s*:\s*(?P<tokens>.+)$")
_NEAR_MISS_PATTERN = re.compile(r"#.*pyrigor", re.IGNORECASE)


def _suppressed_tokens(*, line: str) -> _SuppressionInfo:
    """Get the suppression tokens and optional reason from a source line.

    Args:
        line: One line of source code.

    Returns:
        The suppression information is found on this line, or an empty
        _SuppressionInfo if there is no suppression comment. If a
        comment mentions "pyrigor" but doesn't match the expected
        pattern, a warning is printed.
    """
    match = _SUPPRESSION_PATTERN.search(line)
    if match is None:
        if _NEAR_MISS_PATTERN.search(line):
            print(
                f"Warning: comment mentions 'pyrigor' but doesn't match "
                f"'# pyrigor: CODE[,CODE] # reason' -- ignoring: {line.strip()}",
                file=sys.stderr,
            )
        return _SuppressionInfo(tokens=set(), reason=None)

    body = match.group("tokens")
    codes_part, _, reason_part = body.partition("#")

    tokens = {token.strip() for token in codes_part.split(",")}
    reason = reason_part.strip() or None

    return _SuppressionInfo(tokens=tokens, reason=reason)


def _matches_suppression(*, violation: Violation, suppression: _SuppressionInfo) -> bool:
    """Check whether a violation is suppressed by the given suppression information.

    Args:
        violation: The violation to check.
        suppression: Suppression information parsed from the violation's line.

    Returns:
        True if the violation's rule code, numeric shorthand, or
        symbolic name is present in suppression tokens, and a reason
        is present. Suppression with codes but no reason does not
        suppress. Instead, a warning is printed.
    """
    code = violation.rule.name
    shorthand = code.removeprefix("PYR")
    name = violation.rule.symbolic_name

    code_matches = bool(suppression.tokens & {code, shorthand, name})

    if code_matches and suppression.reason is None:
        print(
            f"Warning: suppression on line {violation.line} for {code} is missing required reason, ignoring.",
            file=sys.stderr,
        )
        return False

    return code_matches


def _line_at(*, lines: list[str], lineno: int) -> str:
    """Get a source line by its 1-based line number.

    Args:
        lines: The source, split into lines.
        lineno: A 1-based line number, possibly out of range.

    Returns:
        The line's text, or an empty string if lineno is out of range.
    """
    return lines[lineno - 1] if 0 < lineno <= len(lines) else ""


def _candidate_lines(*, violation: Violation, lines: list[str]) -> list[str]:
    """Collect every source line where a suppression comment for this violation may legally appear.

    Args:
        violation: The violation to find candidate lines for.
        lines: The full source, split into lines.

    Returns:
        The line directly above the violation, followed by every
        line within the violation's own span (line through 'end_line').
    """
    above = [_line_at(lines=lines, lineno=violation.line - 1)]
    span = [_line_at(lines=lines, lineno=lineno) for lineno in range(violation.line, violation.end_line + 1)]
    return above + span


def _is_suppressed(*, violation: Violation, lines: list[str]) -> bool:
    """Check whether any candidate line for a violation carries a valid suppression comment.

    Args:
        violation: The violation to check.
        lines: The full source, split into lines.

    Returns:
        True if any candidate line has a matching, valid suppression.
    """
    candidates = _candidate_lines(violation=violation, lines=lines)
    return any(
        _matches_suppression(violation=violation, suppression=_suppressed_tokens(line=line)) for line in candidates
    )


def filter_suppressed(*, violations: list[Violation], source: str) -> SuppressionResult:
    """Split violations into kept and suppressed, based on # pyrigor: comments.

    Args:
        violations: Violations to filter.
        source: The source code the violations were found in.

    Returns:
        The violations that are kept, and the ones that were suppressed.
    """
    lines = source.splitlines()

    kept = []
    suppressed = []
    for violation in violations:
        if _is_suppressed(violation=violation, lines=lines):
            suppressed.append(violation)
        else:
            kept.append(violation)

    return SuppressionResult(kept=kept, suppressed=suppressed)
