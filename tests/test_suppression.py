"""Tests for pyrigor's suppression-comment mechanism."""

from pytest import CaptureFixture

from pyrigor.checkers.pyr402_keyword_only_arguments import Violation
from pyrigor.rules import Rule

# noinspection PyProtectedMember
from pyrigor.suppression import (
    _suppressed_tokens,  # pylint: disable=protected-access
    filter_suppressed,
)


def test_suppressed_violation_is_filtered_out() -> None:
    """A violation on a line with a matching # pyrigor: CODE # reason comment should be removed."""
    source = "def apply_correction(weight, bias):  # pyrigor: PYR402 # positional swap risk\n    ...\n"
    violations = [Violation(line=1, column=1, function_name="apply_correction", rule=Rule.PYR402, message="...")]

    result = filter_suppressed(violations=violations, source=source)

    assert not result


def test_unsuppressed_violation_is_kept() -> None:
    """A violation on a line with no suppression comment should be kept."""
    source = "def apply_correction(weight, bias):\n    ...\n"
    violations = [Violation(line=1, column=1, function_name="apply_correction", rule=Rule.PYR402, message="...")]

    result = filter_suppressed(violations=violations, source=source)

    assert result == violations


def test_multiple_suppressed_codes_on_one_line() -> None:
    """Multiple codes in one # pyrigor: comment should each suppress their matching violation."""
    source = "def apply_correction(weight, bias):  # pyrigor: 402,201 # some reason\n    ...\n"
    violations = [
        Violation(line=1, column=1, function_name="apply_correction", rule=Rule.PYR402, message="..."),
    ]

    result = filter_suppressed(violations=violations, source=source)

    assert not result


def test_symbolic_name_suppresses_violation() -> None:
    """A suppression comment using the symbolic name should work, as well as the code."""
    source = "def apply_correction(weight, bias):  # pyrigor: keyword-only-arguments # some reason\n    ...\n"
    violations = [
        Violation(line=1, column=1, function_name="apply_correction", rule=Rule.PYR402, message="..."),
    ]

    result = filter_suppressed(violations=violations, source=source)

    assert not result


def test_whitespace_around_colon_and_commas_is_tolerated() -> None:
    """Irregular spacing around the colon and commas should still parse correctly."""
    source = "def apply_correction(weight, bias):  #pyrigor:  402 , 201 # some reason\n    ...\n"
    violations = [
        Violation(line=1, column=1, function_name="apply_correction", rule=Rule.PYR402, message="..."),
    ]

    result = filter_suppressed(violations=violations, source=source)

    assert not result


def test_suppression_comment_with_reason_is_parsed() -> None:
    """A # pyrigor: CODE # reason comment should suppress and capture the reason text."""
    source = (
        "def apply_correction(weight, bias):  # pyrigor: 402 # pytest fixture injection is positional-only\n    ...\n"
    )
    violations = [
        Violation(line=1, column=1, function_name="apply_correction", rule=Rule.PYR402, message="..."),
    ]

    result = filter_suppressed(violations=violations, source=source)

    assert not result


def test_suppression_comment_reason_is_parsed_correctly() -> None:
    """The free-text reason after the second # should be captured verbatim."""
    line = "def apply_correction(weight, bias):  # pyrigor: 402 # positional injection required by pytest"

    info = _suppressed_tokens(line=line)

    assert info.tokens == {"402"}
    assert info.reason == "positional injection required by pytest"


def test_suppression_without_reason_does_not_suppress(capsys: CaptureFixture[str]) -> None:
    """A suppression comment with no reason should not suppress and should warn."""
    source = "def apply_correction(weight, bias):  # pyrigor: 402\n    ...\n"
    violations = [
        Violation(line=1, column=1, function_name="apply_correction", rule=Rule.PYR402, message="..."),
    ]

    result = filter_suppressed(violations=violations, source=source)

    captured = capsys.readouterr()
    assert result == violations
    assert "missing required reason" in captured.err
