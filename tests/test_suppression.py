"""Tests for pyrigor's suppression-comment mechanism."""

from pytest import CaptureFixture

from pyrigor.rules import Rule

# noinspection PyProtectedMember
from pyrigor.suppression import (
    _suppressed_tokens,  # pylint: disable=protected-access
    filter_suppressed,
)
from pyrigor.violations import Violation


def test_suppressed_violation_is_filtered_out() -> None:
    """A violation on a line with a matching # pyrigor: CODE # reason comment should be removed."""
    source = "def apply_correction(weight, bias):  # pyrigor: PYR402 # positional swap risk\n    ...\n"
    violations = [Violation(line=1, end_line=1, column=1, context_name="apply_correction", rule=Rule.PYR402)]

    result = filter_suppressed(violations=violations, source=source)

    assert not result.kept


def test_unsuppressed_violation_is_kept() -> None:
    """A violation on a line with no suppression comment should be kept."""
    source = "def apply_correction(weight, bias):\n    ...\n"
    violations = [Violation(line=1, end_line=1, column=1, context_name="apply_correction", rule=Rule.PYR402)]

    result = filter_suppressed(violations=violations, source=source)

    assert result.kept == violations


def test_multiple_suppressed_codes_on_one_line() -> None:
    """Multiple codes in one # pyrigor: comment should each suppress their matching violation."""
    source = "def apply_correction(weight, bias):  # pyrigor: 402,201 # some reason\n    ...\n"
    violations = [Violation(line=1, end_line=1, column=1, context_name="apply_correction", rule=Rule.PYR402)]

    result = filter_suppressed(violations=violations, source=source)

    assert not result.kept


def test_symbolic_name_suppresses_violation() -> None:
    """A suppression comment using the symbolic name should work, as well as the code."""
    source = "def apply_correction(weight, bias):  # pyrigor: keyword-only-arguments # some reason\n    ...\n"
    violations = [Violation(line=1, end_line=1, column=1, context_name="apply_correction", rule=Rule.PYR402)]

    result = filter_suppressed(violations=violations, source=source)

    assert not result.kept


def test_whitespace_around_colon_and_commas_is_tolerated() -> None:
    """Irregular spacing around the colon and commas should still parse correctly."""
    source = "def apply_correction(weight, bias):  #pyrigor:  402 , 201 # some reason\n    ...\n"
    violations = [Violation(line=1, end_line=1, column=1, context_name="apply_correction", rule=Rule.PYR402)]

    result = filter_suppressed(violations=violations, source=source)

    assert not result.kept


def test_suppression_comment_with_reason_is_parsed() -> None:
    """A # pyrigor: CODE # reason comment should suppress and capture the reason text."""
    source = (
        "def apply_correction(weight, bias):  # pyrigor: 402 # pytest fixture injection is positional-only\n    ...\n"
    )
    violations = [Violation(line=1, end_line=1, column=1, context_name="apply_correction", rule=Rule.PYR402)]

    result = filter_suppressed(violations=violations, source=source)

    assert not result.kept


def test_suppression_comment_reason_is_parsed_correctly() -> None:
    """The free-text reason after the second # should be captured verbatim."""
    line = "def apply_correction(weight, bias):  # pyrigor: 402 # positional injection required by pytest"

    info = _suppressed_tokens(line=line)

    assert info.tokens == {"402"}
    assert info.reason == "positional injection required by pytest"


def test_suppression_comment_on_line_above_suppresses() -> None:
    """A # pyrigor: CODE # reason comment on the line directly above a violation should suppress it."""
    source = "# pyrigor: 402 # positional injection required by pytest\ndef apply_correction(weight, bias):\n    ...\n"
    violations = [Violation(line=2, end_line=2, column=1, context_name="apply_correction", rule=Rule.PYR402)]

    result = filter_suppressed(violations=violations, source=source)

    assert not result.kept
    assert result.suppressed == violations


def test_same_line_match_suppresses_even_when_line_above_has_different_code() -> None:
    """A matching same-line suppression should still suppress even when the line above has a different code."""
    source = (
        "# pyrigor: 403 # wrong rule, should be ignored\n"
        "def apply_correction(weight, bias):  # pyrigor: 402 # correct rule, same line\n"
        "    ...\n"
    )
    violations = [Violation(line=2, end_line=2, column=1, context_name="apply_correction", rule=Rule.PYR402)]

    result = filter_suppressed(violations=violations, source=source)

    assert not result.kept
    assert result.suppressed == violations


def test_line_above_suppression_at_the_very_first_line_does_not_crash() -> None:
    """A violation on line 1 has no line above it. Checking should not crash (index out of range)."""
    source = "def apply_correction(weight, bias):\n    ...\n"
    violations = [Violation(line=1, end_line=1, column=1, context_name="apply_correction", rule=Rule.PYR402)]

    result = filter_suppressed(violations=violations, source=source)

    assert result.kept == violations
    assert not result.suppressed


def test_line_above_with_wrong_code_does_not_suppress() -> None:
    """A line-above comment for a different rule should not suppress an unrelated violation."""
    source = "# pyrigor: 403 # unrelated rule\ndef apply_correction(weight, bias):\n    ...\n"
    violations = [Violation(line=2, end_line=2, column=1, context_name="apply_correction", rule=Rule.PYR402)]

    result = filter_suppressed(violations=violations, source=source)

    assert result.kept == violations
    assert not result.suppressed


# pyrigor: 403 # pytest fixture injection, not a real violation
def test_line_above_without_reason_does_not_suppress(capsys: CaptureFixture[str]) -> None:
    """A line-above suppression comment missing a reason should not suppress and should warn."""
    source = "# pyrigor: 402\ndef apply_correction(weight, bias):\n    ...\n"
    violations = [Violation(line=2, end_line=2, column=1, context_name="apply_correction", rule=Rule.PYR402)]

    result = filter_suppressed(violations=violations, source=source)

    captured = capsys.readouterr()
    assert result.kept == violations
    assert "missing required reason" in captured.err


def test_same_line_suppression_works_when_stacked_after_nosec() -> None:
    """Pyrigor's own same-line suppression still works when another tool's comment precedes it."""
    source = "def apply_correction(weight, bias):  # nosec  # pyrigor: 402 # positional swap risk\n    ...\n"
    violations = [Violation(line=1, end_line=1, column=1, context_name="apply_correction", rule=Rule.PYR402)]

    result = filter_suppressed(violations=violations, source=source)

    assert not result.kept
    assert result.suppressed == violations


def test_line_above_suppression_works_when_stacked_after_complexipy_ignore() -> None:
    """Pyrigor's own line-above suppression still works when another tool's comment precedes it on that line."""
    source = (
        "# complexipy: ignore  # pyrigor: 402 # positional swap risk\ndef apply_correction(weight, bias):\n    ...\n"
    )
    violations = [Violation(line=2, end_line=2, column=1, context_name="apply_correction", rule=Rule.PYR402)]

    result = filter_suppressed(violations=violations, source=source)

    assert not result.kept
    assert result.suppressed == violations


# pyrigor: 403 # pytest fixture injection, not a real violation
def test_bare_other_tool_comment_on_line_above_does_not_suppress_or_warn(capsys: CaptureFixture[str]) -> None:
    """A line-above comment belonging to another tool alone should not suppress and should not warn either."""
    source = "# nosec\ndef apply_correction(weight, bias):\n    ...\n"
    violations = [Violation(line=2, end_line=2, column=1, context_name="apply_correction", rule=Rule.PYR402)]

    result = filter_suppressed(violations=violations, source=source)

    captured = capsys.readouterr()
    assert result.kept == violations
    assert not result.suppressed
    assert captured.err == ""


def test_pyrigor_comment_before_other_tool_comment_still_suppresses_despite_polluted_reason() -> None:
    """Pyrigor's comment before another tool's still suppresses, despite a polluted reason (a known limitation)."""
    source = "def apply_correction(weight, bias):  # pyrigor: 402 # positional swap risk  # nosec\n    ...\n"
    violations = [Violation(line=1, end_line=1, column=1, context_name="apply_correction", rule=Rule.PYR402)]

    result = filter_suppressed(violations=violations, source=source)

    assert not result.kept
    assert result.suppressed == violations


def test_suppression_comment_on_closing_line_of_multiline_statement_suppresses() -> None:
    """A suppression comment on the closing line of a multi-line statement should suppress it."""
    source = "compute_total(\n    items,\n)  # pyrigor: 406 # testing multi-line suppression\n"
    violations = [Violation(line=1, end_line=3, column=1, context_name="compute_total", rule=Rule.PYR406)]

    result = filter_suppressed(violations=violations, source=source)

    assert not result.kept


def test_suppression_comment_on_middle_line_of_multiline_statement_suppresses() -> None:
    """A suppression comment on a middle line of a multi-line statement's span should suppress it."""
    source = "compute_total(\n    items,  # pyrigor: 406 # testing multi-line suppression\n)\n"
    violations = [Violation(line=1, end_line=3, column=1, context_name="compute_total", rule=Rule.PYR406)]

    result = filter_suppressed(violations=violations, source=source)

    assert not result.kept


def test_suppression_comment_two_lines_above_does_not_suppress() -> None:
    """A suppression comment more than one line above a violation should not suppress it."""
    source = "# pyrigor: 402 # reason\n\ndef apply_correction(weight, bias):\n    ...\n"
    violations = [Violation(line=3, end_line=3, column=1, context_name="apply_correction", rule=Rule.PYR402)]

    result = filter_suppressed(violations=violations, source=source)

    assert result.kept == violations


def test_suppression_comment_after_statement_span_does_not_suppress() -> None:
    """A suppression comment on a line after a multi-line statement's own span should not suppress it."""
    source = "compute_total(\n    items,\n)\n# pyrigor: 406 # reason\n"
    violations = [Violation(line=1, end_line=3, column=1, context_name="compute_total", rule=Rule.PYR406)]

    result = filter_suppressed(violations=violations, source=source)

    assert result.kept == violations


def test_violation_with_out_of_range_end_line_is_kept_not_crashed() -> None:
    """A violation whose 'end_line' exceeds the source's actual length should be kept, not crash."""
    source = "def apply_correction(weight, bias):\n    ...\n"
    violations = [Violation(line=1, end_line=999, column=1, context_name="apply_correction", rule=Rule.PYR402)]

    result = filter_suppressed(violations=violations, source=source)

    assert result.kept == violations


# pyrigor: 403 # pytest fixture injection, not a real violation
def test_suppression_without_reason_does_not_suppress(capsys: CaptureFixture[str]) -> None:
    """A suppression comment with no reason should not suppress and should warn."""
    source = "def apply_correction(weight, bias):  # pyrigor: 402\n    ...\n"
    violations = [Violation(line=1, end_line=1, column=1, context_name="apply_correction", rule=Rule.PYR402)]

    result = filter_suppressed(violations=violations, source=source)

    captured = capsys.readouterr()
    assert result.kept == violations
    assert "missing required reason" in captured.err


# pyrigor: 403 # pytest fixture injection, not a real violation
def test_near_miss_comment_warns(capsys: CaptureFixture[str]) -> None:
    """A comment mentioning 'pyrigor' that doesn't match the suppression pattern should warn."""
    hash_char = "#"
    source = f"def apply_correction(weight, bias):  {hash_char} pyrigor 402 missing colon\n    ...\n"
    violations = [Violation(line=1, end_line=1, column=1, context_name="apply_correction", rule=Rule.PYR402)]

    result = filter_suppressed(violations=violations, source=source)

    captured = capsys.readouterr()
    assert result.kept == violations
    assert "doesn't match" in captured.err


def test_violation_with_out_of_range_line_number_is_kept_not_crashed() -> None:
    """A violation whose line number exceeds the source's actual length should be kept, not crash."""
    source = "def apply_correction(weight, bias):\n    ...\n"
    violations = [Violation(line=999, end_line=999, column=1, context_name="apply_correction", rule=Rule.PYR402)]

    result = filter_suppressed(violations=violations, source=source)

    assert result.kept == violations
    assert not result.suppressed
