"""Tests for pyrigor's suppression-comment mechanism."""
# test assertions compare against expected literal values by design,
# not a magic-value problem
# pylint: disable=magic-value-comparison

import tokenize
from io import StringIO
from typing import NamedTuple

import pytest

from pyrigor.rules import Rule

# noinspection PyProtectedMember
from pyrigor.suppression import (
    _suppressed_tokens,  # pyright: ignore[reportPrivateUsage]
    filter_suppressed,
)
from tests.checker_helpers import finding_at


@pytest.mark.parametrize("as_iterator", [False, True])
def test_cached_tokens_do_not_require_an_unused_source_argument(*, as_iterator: bool) -> None:
    """The pipeline can pass its single shared stream without retaining a redundant source argument."""
    source = "# pyrigor 402 # reason\ndef flagged(a, b): pass\n"
    findings = [finding_at(line=2, end_line=2, column=1, rule=Rule.PYR402)]
    tokens = tuple(tokenize.generate_tokens(StringIO(source).readline))
    result = filter_suppressed(findings=findings, tokens=iter(tokens) if as_iterator else tokens)
    assert result.kept == []
    assert result.suppressed == findings
    assert result.errors == ()


def test_nonempty_findings_require_a_suppression_input() -> None:
    """Missing text and tokens is a caller error, while an empty list needs no tokenisation."""
    assert not filter_suppressed(findings=[]).kept
    with pytest.raises(ValueError, match=r"^suppression requires source text or tokens$"):
        filter_suppressed(findings=[finding_at(line=1, end_line=1, column=1, rule=Rule.PYR402)])


class _CommentCase(NamedTuple):
    """A raw comment and its expected partition sizes and located warnings."""

    comment: str
    kept: int
    suppressed: int
    errors: tuple[tuple[str, int, int], ...]


# noinspection IncorrectFormatting
@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
@pytest.mark.parametrize(
    "case",
    [
        _CommentCase("# pyrigor 402 # reason", 0, 1, ()),
        _CommentCase(
            "# pyrigor: 402 # reason",
            1,
            0,
            (
                (
                    (
                        "comment mentions 'pyrigor' but does not match '# pyrigor CODE[,CODE] # reason' "
                        "-- ignoring: # pyrigor: 402 # reason"
                    ),
                    3,
                    1,
                ),
            ),
        ),
        _CommentCase("# unrelated", 1, 0, ()),
    ],
)
def test_raw_line_breaks_preserve_comment_boundaries(
    *,
    newline: str,
    case: _CommentCase,
) -> None:
    """Standalone suppression scanning uses Python line breaks and retains warning text."""
    comment, kept, suppressed, errors = case
    source = newline.join(["pass", "pass", comment, "def flagged(a, b): pass", ""])
    findings = [finding_at(line=4, end_line=4, column=1, rule=Rule.PYR402)]
    result = filter_suppressed(findings=findings, source=source)
    assert (
        len(result.kept),
        len(result.suppressed),
        result.kept + result.suppressed,
        tuple((error.message, error.line, error.column) for error in result.errors),
    ) == (kept, suppressed, findings, errors)


def test_suppressed_violation_is_filtered_out() -> None:
    """A violation on a line with a matching # pyrigor CODE # reason comment should be removed."""
    source = "def apply_correction(weight, bias):  # pyrigor PYR402 # positional swap risk\n    ...\n"
    findings = [
        finding_at(line=1, end_line=1, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert not result.kept


def test_unsuppressed_violation_is_kept() -> None:
    """A violation on a line with no suppression comment should be kept."""
    source = "def apply_correction(weight, bias):\n    ...\n"
    findings = [
        finding_at(line=1, end_line=1, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert result.kept == findings


def test_multiple_suppressed_codes_on_one_line() -> None:
    """Multiple codes in one # pyrigor comment should each suppress their matching violation."""
    source = "def apply_correction(weight, bias):  # pyrigor 402,201 # some reason\n    ...\n"
    findings = [
        finding_at(line=1, end_line=1, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert not result.kept


def test_symbolic_name_suppresses_violation() -> None:
    """A suppression comment using the symbolic name should work, as well as the code."""
    source = "def apply_correction(weight, bias):  # pyrigor keyword-only-arguments # some reason\n    ...\n"
    findings = [
        finding_at(line=1, end_line=1, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert not result.kept


def test_whitespace_around_pyrigor_and_commas_is_tolerated() -> None:
    """Irregular spacing after 'pyrigor' and around commas should still parse correctly."""
    source = "def apply_correction(weight, bias):  #pyrigor   402 , 201 # some reason\n    ...\n"
    findings = [
        finding_at(line=1, end_line=1, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert not result.kept


def test_suppression_comment_with_reason_is_parsed() -> None:
    """A # pyrigor CODE # reason comment should suppress and capture the reason text."""
    source = (
        "def apply_correction(weight, bias):  # pyrigor 402 # pytest fixture injection is positional-only\n    ...\n"
    )
    findings = [
        finding_at(line=1, end_line=1, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert not result.kept


def test_suppression_comment_reason_is_parsed_correctly() -> None:
    """The free-text reason after the second # should be captured verbatim."""
    comment = "# pyrigor 402 # positional injection required by pytest"

    info = _suppressed_tokens(comment=comment)

    assert info is not None
    assert info.tokens == {"402"}
    assert info.reason == "positional injection required by pytest"


def test_suppression_comment_on_line_above_suppresses() -> None:
    """A # pyrigor CODE # reason comment on the line directly above a violation should suppress it."""
    source = "# pyrigor 402 # positional injection required by pytest\ndef apply_correction(weight, bias):\n    ...\n"
    findings = [
        finding_at(line=2, end_line=2, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert not result.kept
    assert result.suppressed == findings


def test_same_line_match_suppresses_even_when_line_above_has_different_code() -> None:
    """The matching same-line suppression should still suppress even when the line above has a different code."""
    source = (
        "# pyrigor 403 # wrong rule, should be ignored\n"
        "def apply_correction(weight, bias):  # pyrigor 402 # correct rule, same line\n"
        "    ...\n"
    )
    findings = [
        finding_at(line=2, end_line=2, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert not result.kept
    assert result.suppressed == findings


def test_line_above_suppression_at_the_very_first_line_does_not_crash() -> None:
    """A violation on line 1 has no line above it. Checking should not crash (index out of range)."""
    source = "def apply_correction(weight, bias):\n    ...\n"
    findings = [
        finding_at(line=1, end_line=1, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert result.kept == findings
    assert not result.suppressed


def test_line_above_with_wrong_code_does_not_suppress() -> None:
    """A line-above comment for a different rule should not suppress an unrelated violation."""
    source = "# pyrigor 403 # unrelated rule\ndef apply_correction(weight, bias):\n    ...\n"
    findings = [
        finding_at(line=2, end_line=2, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert result.kept == findings
    assert not result.suppressed


def test_line_above_without_reason_does_not_suppress() -> None:
    """A line-above suppression comment missing a reason should not suppress and should warn."""
    source = "# pyrigor 402\ndef apply_correction(weight, bias):\n    ...\n"
    findings = [
        finding_at(line=2, end_line=2, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert result.kept == findings
    assert any("missing required reason" in error.message for error in result.errors)


def test_same_line_suppression_works_when_stacked_after_nosec() -> None:
    """The pyrigor same-line suppression still works when another tool's comment precedes it."""
    source = "def apply_correction(weight, bias):  # nosec  # pyrigor 402 # positional swap risk\n    ...\n"
    findings = [
        finding_at(line=1, end_line=1, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert not result.kept
    assert result.suppressed == findings


def test_line_above_suppression_works_when_stacked_after_complexipy_ignore() -> None:
    """The pyrigor line-above suppression still works when another tool's comment precedes it on that line."""
    source = (
        "# complexipy: ignore  # pyrigor 402 # positional swap risk\ndef apply_correction(weight, bias):\n    ...\n"
    )
    findings = [
        finding_at(line=2, end_line=2, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert not result.kept
    assert result.suppressed == findings


def test_bare_other_tool_comment_on_line_above_does_not_suppress_or_warn() -> None:
    """A line-above comment belonging to another tool alone should not suppress and should not warn either."""
    source = "# nosec\ndef apply_correction(weight, bias):\n    ...\n"
    # Intentional duplicated fixture for independent suppression regression coverage.
    # noinspection DuplicatedCode
    findings = [
        finding_at(line=2, end_line=2, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert result.kept == findings
    assert not result.suppressed
    assert not result.errors


def test_pyrigor_comment_before_other_tool_comment_still_suppresses_despite_polluted_reason() -> None:
    """A pyrigor comment before another tool's still suppresses, despite a polluted reason (a known limitation)."""
    source = "def apply_correction(weight, bias):  # pyrigor 402 # positional swap risk  # nosec\n    ...\n"
    findings = [
        finding_at(line=1, end_line=1, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert not result.kept
    assert result.suppressed == findings


def test_suppression_comment_on_closing_line_of_multiline_statement_suppresses() -> None:
    """A suppression comment on the closing line of a multi-line statement should suppress it."""
    source = "compute_total(\n    items,\n)  # pyrigor 406 # testing multi-line suppression\n"
    findings = [
        finding_at(line=1, end_line=3, column=1, rule=Rule.PYR406),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert not result.kept


def test_suppression_comment_on_middle_line_of_multiline_statement_suppresses() -> None:
    """A suppression comment on a middle line of a multi-line statement's span should suppress it."""
    source = "compute_total(\n    items,  # pyrigor 406 # testing multi-line suppression\n)\n"
    findings = [
        finding_at(line=1, end_line=3, column=1, rule=Rule.PYR406),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert not result.kept


def test_suppression_comment_two_lines_above_does_not_suppress() -> None:
    """A suppression comment more than one line above a violation should not suppress it."""
    source = "# pyrigor 402 # reason\n\ndef apply_correction(weight, bias):\n    ...\n"
    findings = [
        finding_at(line=3, end_line=3, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert result.kept == findings


def test_suppression_comment_after_statement_span_does_not_suppress() -> None:
    """A suppression comment on a line after a multi-line statement's own span should not suppress it."""
    source = "compute_total(\n    items,\n)\n# pyrigor 406 # reason\n"
    findings = [
        finding_at(line=1, end_line=3, column=1, rule=Rule.PYR406),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert result.kept == findings


def test_violation_with_out_of_range_end_line_is_kept_not_crashed() -> None:
    """A violation whose 'end_line' exceeds the source's actual length should be kept, not crash."""
    source = "def apply_correction(weight, bias):\n    ...\n"
    findings = [
        finding_at(line=1, end_line=999, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert result.kept == findings


def test_suppression_without_reason_does_not_suppress() -> None:
    """A suppression comment with no reason should not suppress and should warn."""
    source = "def apply_correction(weight, bias):  # pyrigor 402\n    ...\n"
    findings = [
        finding_at(line=1, end_line=1, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert result.kept == findings
    assert any("missing required reason" in error.message for error in result.errors)


def test_near_miss_comment_warns() -> None:
    """The old colon-based suppression syntax now near-misses and warns, rather than silently doing nothing."""
    hash_char = "#"
    source = f"def apply_correction(weight, bias):  {hash_char} pyrigor: 402 # old syntax\n    ...\n"
    findings = [
        finding_at(line=1, end_line=1, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert result.kept == findings
    assert any("does not match" in error.message for error in result.errors)


def test_near_miss_pattern_inside_a_string_literal_does_not_warn() -> None:
    """A string literal that merely contains near-miss-shaped text must not trigger a near-miss warning.

    Reproduces the actual bug found scanning tests/ for the first
    time: a near-miss warning fired on a test's own fixture string
    containing literal "# pyrigor" text, not a real comment.
    """
    source = 'fixture = "# pyrigor 402 missing colon"\ndef apply_correction(weight, bias):\n    ...\n'
    # Intentional duplicated fixture for independent suppression regression coverage.
    # noinspection DuplicatedCode
    findings = [
        finding_at(line=2, end_line=2, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert result.kept == findings
    assert not result.errors


def test_pyrigor_suppression_syntax_inside_a_string_literal_does_not_suppress() -> None:
    """A string literal that exactly matches suppression syntax must not silently suppress a violation.

    The more serious risk the near-miss bug revealed: a string whose
    contents happen to exactly match '# pyrigor CODE # reason' would
    not just warn, it could silently suppress a real violation on
    that line, since raw-regular expression scanning cannot tell a real comment
    from text that merely looks like one inside a string.
    """
    source = (
        'fixture = "# pyrigor 402 # this looks like a real suppression but is just string data"\n'
        "def apply_correction(weight, bias):\n"
        "    ...\n"
    )
    findings = [
        finding_at(line=2, end_line=2, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert result.kept == findings
    assert not result.suppressed


def test_real_suppression_comment_still_works_despite_a_similar_looking_string_earlier_on_the_line() -> None:
    """A real suppression comment must still work even when preceded by string text that looks similar."""
    source = 'note = "# pyrigor 999 fake"  # pyrigor 402 # real reason\ndef apply_correction(weight, bias):\n    ...\n'
    findings = [
        finding_at(line=2, end_line=2, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert not result.kept
    assert result.suppressed == findings


def test_filter_suppressed_with_no_violations_does_not_tokenize_unparsable_source() -> None:
    """An empty findings list should short-circuit before ever tokenising the source.

    Guards the precondition 'filter_suppressed' relies on: findings
    are only ever non-empty for a source that already parsed
    successfully via ast.parse, so tokenising is safe to skip
    entirely when there is nothing to check — including for
    a genuinely unparsable source, which would otherwise crash
    tokenising.
    """
    source = "def broken(:\n    pass\n"

    result = filter_suppressed(findings=[], source=source)

    assert not result.kept
    assert not result.suppressed


def test_violation_with_out_of_range_line_number_is_kept_not_crashed() -> None:
    """A violation whose line number exceeds the source's actual length should be kept, not crash."""
    source = "def apply_correction(weight, bias):\n    ...\n"
    findings = [
        finding_at(line=999, end_line=999, column=1, rule=Rule.PYR402),
    ]

    result = filter_suppressed(findings=findings, source=source)

    assert result.kept == findings
    assert not result.suppressed
