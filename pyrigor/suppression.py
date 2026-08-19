"""Suppression-comment mechanism for pyrigor's checkers.

Recognizes `# pyrigor: CODE[, CODE...]` comments on the same line as a
violation, on the line directly above it, or anywhere within a
multi-line statement's own span. CODE may be a rule's full code
("PYR402"), its numeric shorthand ("402"), or its symbolic name
("keyword-only-arguments"). Whitespace around the colon and commas is
tolerated. Only text inside a genuine comment token counts — text
that merely looks like a suppression comment inside a string or
docstring is never recognized.
"""

import re
import sys
import tokenize
from io import StringIO
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


def _comments_by_line(*, source: str) -> dict[int, str]:
    """Map each physical line number to its genuine comment token text.

    Args:
        source: The full source code. Only called when at least one
            violation exists, which guarantees the source already
            parsed successfully via ast.parse (checkers never run on
            an unparsable source) — and anything ast.parse accepts,
            tokenize accepts too.

    Returns:
        A line-number-to-comment-text mapping, built from real
        tokenizing.COMMENT tokens only — never text that merely looks
        like a comment inside a string or docstring.
    """
    tokens = tokenize.generate_tokens(StringIO(source).readline)
    return {token.start[0]: token.string for token in tokens if token.type == tokenize.COMMENT}


def _suppressed_tokens(*, comment: str) -> _SuppressionInfo:
    """Get the suppression tokens and optional reason from a genuine comment.

    Args:
        comment: A real comment token's text (for example "# pyrigor: CODE
            # reason"), or "" if the line has no comment at all.

    Returns:
        The suppression information is found in this comment, or an
        empty _SuppressionInfo if there is none. If the comment
        mentions "pyrigor" but doesn't match the expected pattern, a
        warning is printed.
    """
    match = _SUPPRESSION_PATTERN.search(comment)
    if match is None:
        if _NEAR_MISS_PATTERN.search(comment):
            print(
                f"Warning: comment mentions 'pyrigor' but doesn't match "
                f"'# pyrigor: CODE[,CODE] # reason' -- ignoring: {comment.strip()}",
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
        suppression: Suppression information parsed from a candidate comment.

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


def _candidate_comments(*, violation: Violation, comments: dict[int, str]) -> list[str]:
    """Collect every comment where a suppression comment for this violation may legally appear.

    Args:
        violation: The violation to find candidate comments for.
        comments: The file's line-number-to-comment-text mapping.

    Returns:
        The comment on the line directly above the violation,
        followed by the comment on every line within the violation's
        own span (line through 'end_line'). A missing dict entry
        (no comment on that line, or the line doesn't exist) yields "".
    """
    above = [comments.get(violation.line - 1, "")]
    span = [comments.get(lineno, "") for lineno in range(violation.line, violation.end_line + 1)]
    return above + span


def _is_suppressed(*, violation: Violation, comments: dict[int, str]) -> bool:
    """Check whether any candidate comment for a violation carries valid suppression.

    Args:
        violation: The violation to check.
        comments: The file's line-number-to-comment-text mapping.

    Returns:
        True if any candidate comment has matching, valid suppression.
    """
    candidates = _candidate_comments(violation=violation, comments=comments)
    return any(
        _matches_suppression(violation=violation, suppression=_suppressed_tokens(comment=comment))
        for comment in candidates
    )


def filter_suppressed(*, violations: list[Violation], source: str) -> SuppressionResult:
    """Split violations into kept and suppressed, based on # pyrigor: comments.

    Args:
        violations: Violations to filter.
        source: The source code the violations were found in.

    Returns:
        The violations that are kept, and the ones that were suppressed.
    """
    if not violations:
        return SuppressionResult(kept=[], suppressed=[])

    comments = _comments_by_line(source=source)

    kept = []
    suppressed = []
    for violation in violations:
        if _is_suppressed(violation=violation, comments=comments):
            suppressed.append(violation)
        else:
            kept.append(violation)

    return SuppressionResult(kept=kept, suppressed=suppressed)
