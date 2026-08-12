"""Suppression-comment mechanism for pyrigor's checkers.

Recognizes `# pyrigor: CODE[, CODE...]` comments on the same line as a
violation, where CODE may be a rule's full code ("PYR402"), its
numeric shorthand ("402"), or its symbolic name
("keyword-only-arguments"). Whitespace around the colon and commas is
tolerated.
"""

import re
from typing import NamedTuple
from pyrigor.checkers.pyr402_keyword_only_arguments import Violation


class _SuppressionInfo(NamedTuple):
    """Parsed contents of a `# pyrigor:` suppression comment."""

    tokens: set[str]
    reason: str | None


_SUPPRESSION_PATTERN = re.compile(r"#\s*pyrigor\s*:\s*(?P<tokens>.+)$")


def _suppressed_tokens(*, line: str) -> _SuppressionInfo:
    """Get the suppression tokens and optional reason from a source line.

    Args:
        line: One line of source code.

    Returns:
        The suppression information, which is found on this line, or an empty
        _SuppressionInfo if there is no suppression comment.
    """
    match = _SUPPRESSION_PATTERN.search(line)
    if match is None:
        return _SuppressionInfo(tokens=set(), reason=None)

    body = match.group("tokens")
    codes_part, _, reason_part = body.partition("#")

    tokens = {token.strip() for token in codes_part.split(",")}
    reason = reason_part.strip() or None

    return _SuppressionInfo(tokens=tokens, reason=reason)


def _matches_suppression(*, violation: Violation, tokens: set[str]) -> bool:
    """Check whether a violation is suppressed by the given tokens.

    Args:
        violation: The violation to check.
        tokens: Suppression tokens, which are found on the violation's line.

    Returns:
        True if the violation's rule code, numeric shorthand, or
        symbolic name is present in tokens.
    """
    code = violation.rule.name  # "PYR402"
    shorthand = code.removeprefix("PYR")  # "402"
    name = violation.rule.value  # "keyword-only-arguments"

    return bool(tokens & {code, shorthand, name})


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

        if not _matches_suppression(violation=violation, tokens=suppression.tokens):
            result.append(violation)

    return result
