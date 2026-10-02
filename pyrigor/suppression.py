"""Partition findings using real comments besides their primary spans."""

import re
import tokenize
from collections.abc import Iterable
from io import StringIO
from typing import Final, NamedTuple

from pyrigor.diagnostics import CheckError
from pyrigor.findings import FileName, Finding, Span

_SUPPRESSION_PATTERN: Final = re.compile(r"#\s*pyrigor\s+(?P<tokens>.+)$")
_NEAR_MISS_PATTERN: Final = re.compile(r"#\s*pyrigor\b", re.IGNORECASE)


class _SuppressionInfo(NamedTuple):
    """Code tokens and the required reason from one comment."""

    tokens: set[str]
    reason: str | None


class SuppressionResult(NamedTuple):
    """Kept findings, suppressed findings and malformed comment warnings."""

    kept: list[Finding]
    suppressed: list[Finding]
    errors: tuple[CheckError, ...] = ()


def _comments_by_line(*, source: str, tokens: Iterable[tokenize.TokenInfo] | None) -> dict[int, tokenize.TokenInfo]:
    """Exclude comment-shaped text inside strings and normalise Python line breaks."""
    if tokens is None:
        normalised = source.replace("\r\n", "\n").replace("\r", "\n")
        tokens = tokenize.generate_tokens(StringIO(normalised).readline)
    return {token.start[0]: token for token in tokens if token.type == tokenize.COMMENT}


def _suppressed_tokens(*, comment: str) -> _SuppressionInfo | None:
    """Parse exact pyrigor syntax, leaving malformed syntax to the caller."""
    match = _SUPPRESSION_PATTERN.search(comment)
    if match is None:
        return None
    body, _, reason = match.group("tokens").partition("#")
    return _SuppressionInfo(tokens={token.strip() for token in body.split(",")}, reason=reason.strip() or None)


def _candidate_comments(*, primary: Span, comments: dict[int, tokenize.TokenInfo]) -> list[tokenize.TokenInfo]:
    """Allow the immediately preceding line and all lines touched by the primary span."""
    return [comments[line] for line in range(max(1, primary.line_start - 1), primary.line_end + 1) if line in comments]


def _comment_error(*, comment: tokenize.TokenInfo, primary: Span, message: str) -> CheckError:
    """Locate a warning at the actual comment in code-point columns."""
    return CheckError(
        file_name=FileName(primary.file_name),
        kind="malformed_suppression",
        message=message,
        line=comment.start[0],
        column=comment.start[1] + 1,
    )


def _matches_comment(
    *, finding: Finding, primary: Span, comment: tokenize.TokenInfo, errors: dict[CheckError, None]
) -> bool:
    """Record malformed comments and honour matching codes only when a reason exists."""
    info = _suppressed_tokens(comment=comment.string)
    if info is None:
        if _NEAR_MISS_PATTERN.search(comment.string):
            message = (
                "comment mentions 'pyrigor' but does not match '# pyrigor CODE[,CODE] # reason' "
                f"-- ignoring: {comment.string}"
            )
            errors[_comment_error(comment=comment, primary=primary, message=message)] = None
        return False
    code = finding.code
    if not info.tokens.intersection({code.name, code.name.removeprefix("PYR"), code.symbolic_name}):
        return False
    if info.reason is None:
        message = f"suppression on line {primary.line_start} for {code.name} is missing required reason, ignoring."
        errors[_comment_error(comment=comment, primary=primary, message=message)] = None
        return False
    return True


def _is_suppressed(
    *, finding: Finding, comments: dict[int, tokenize.TokenInfo], errors: dict[CheckError, None]
) -> bool:
    """Inspect every candidate so valid suppressions cannot hide malformed comments."""
    primary = next(span for span in finding.spans if span.is_primary)
    matches = [
        _matches_comment(finding=finding, primary=primary, comment=comment, errors=errors)
        for comment in _candidate_comments(primary=primary, comments=comments)
    ]
    return any(matches)


def filter_suppressed(
    *, findings: list[Finding], source: str, tokens: Iterable[tokenize.TokenInfo] | None = None
) -> SuppressionResult:
    """Partition canonical findings and return warnings for the CLI to report."""
    if not findings:
        return SuppressionResult(kept=[], suppressed=[])
    comments = _comments_by_line(source=source, tokens=tokens)
    kept: list[Finding] = []
    suppressed: list[Finding] = []
    errors: dict[CheckError, None] = {}
    for finding in findings:
        destination = suppressed if _is_suppressed(finding=finding, comments=comments, errors=errors) else kept
        destination.append(finding)
    return SuppressionResult(kept=kept, suppressed=suppressed, errors=tuple(errors))
