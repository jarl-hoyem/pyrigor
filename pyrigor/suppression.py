"""Suppression-comment mechanism for pyrigor's checkers.

Recognizes `# pyrigor: CODE[, CODE...]` comments on the same line as a
violation, where CODE may be a rule's full code ("PYR402"), its
numeric shorthand ("402"), or its symbolic name
("keyword-only-arguments"). Whitespace around the colon and commas is
tolerated.
"""

import re

from pyrigor.checkers.pyr402_keyword_only_arguments import Violation

_SUPPRESSION_PATTERN = re.compile(r"#\s*pyrigor\s*:\s*(?P<tokens>.+)$")


def _suppressed_tokens(*, line: str) -> set[str]:
    """Extracts the suppression tokens from a single source line.

    Args:
        line: One line of source code.

    Returns:
        The tokens, which are listed after `# pyrigor:` on this line, or
        an empty set if there is no suppression comment.
    """
    match = _SUPPRESSION_PATTERN.search(line)
    if match is None:
        return set()

    return {token.strip() for token in match.group("tokens").split(",")}


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
        tokens = _suppressed_tokens(line=line_text)

        if not _matches_suppression(violation=violation, tokens=tokens):
            result.append(violation)

    return result
