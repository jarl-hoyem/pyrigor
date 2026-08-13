"""Suppression-comment mechanism for pyrigor's checkers.

Recognizes `# pyrigor: CODE[, CODE...]` comments on the same line as a
violation, where CODE may be a rule's full code ("PYR402"), its
numeric shorthand ("402"), or its symbolic name
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
    name = violation.rule.value

    code_matches = bool(suppression.tokens & {code, shorthand, name})

    if code_matches and suppression.reason is None:
        print(
            f"Warning: suppression on line {violation.line} for {code} is missing required reason, ignoring.",
            file=sys.stderr,
        )
        return False

    return code_matches


def filter_suppressed(*, violations: list[Violation], source: str) -> list[Violation]:
    """Remove violations suppressed by a same-line `# pyrigor:` comment.

    Args:
        violations: Violations to filter.
        source: The source code the violations were found in.

    Returns:
        Violations that are not suppressed.
    """
    lines = source.splitlines()

    result = []
    for violation in violations:
        line_text = lines[violation.line - 1] if 0 < violation.line <= len(lines) else ""
        suppression = _suppressed_tokens(line=line_text)

        if not _matches_suppression(violation=violation, suppression=suppression):
            result.append(violation)

    return result
