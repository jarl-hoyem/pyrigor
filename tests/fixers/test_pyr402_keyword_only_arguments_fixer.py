"""Tests for the opt-in PYR402 fixer."""
# pylint: disable=magic-value-comparison

from typing import SupportsIndex

import pytest

from pyrigor.fixers.pyr402_keyword_only_arguments_fixer import FixRejectedError, FixStatus, fix_source
from tests.line_breaks import LINE_BREAK_IDS, NON_PYTHON_LINE_BREAKS


def test_adds_bare_star_before_positional_parameters() -> None:
    """A regular function's positional parameters become keyword-only."""
    source = "def apply_correction(weight, bias):\n    return weight + bias\n"

    result = fix_source(source=source)

    assert result.source == "def apply_correction(*, weight, bias):\n    return weight + bias\n"
    assert result.status is FixStatus.CHANGED


def test_preserves_self_before_keyword_only_parameters() -> None:
    """Methods retain the conventional leading self parameter."""
    source = "class Corrector:\n    def apply(self, weight, bias):\n        return weight + bias\n"

    result = fix_source(source=source)

    assert result.source == "class Corrector:\n    def apply(self, *, weight, bias):\n        return weight + bias\n"
    assert result.status is FixStatus.CHANGED


def test_leaves_single_parameter_method_unchanged() -> None:
    """A method with one parameter after self belongs to PYR403, not PYR402."""
    source = "class Corrector:\n    def apply(self, weight):\n        return weight\n"

    result = fix_source(source=source)

    assert result.source == source
    assert result.status is FixStatus.UNCHANGED


def test_leaves_single_parameter_dunder_method_unchanged() -> None:
    """A positional protocol method outside PYR402 must retain its runtime semantics."""
    source = "class Value:\n    def __eq__(self, other):\n        return True\n"

    result = fix_source(source=source)

    assert result.source == source
    assert result.status is FixStatus.UNCHANGED


def test_leaves_suppressed_pyr402_function_unchanged() -> None:
    """The fixer must honour the same suppression comments as the checker."""
    source = "def callback(left, right):  # pyrigor 402 # external callback contract\n    return left\n"

    result = fix_source(source=source)

    assert result.source == source
    assert result.status is FixStatus.UNCHANGED


def test_dry_run_does_not_return_a_modified_source() -> None:
    """Dry-run mode reports the prospective edit without changing the source."""
    source = "def apply(weight, bias):\n    pass\n"

    result = fix_source(source=source, dry_run=True)

    assert result.source == source
    assert result.status is FixStatus.WOULD_CHANGE


def test_preserves_crlf_line_endings() -> None:
    """A fixer must preserve the input line-ending convention."""
    source = b"def apply(weight, bias):\r\n    pass\r\n"

    result = fix_source(source=source)

    assert result.source == b"def apply(*, weight, bias):\r\n    pass\r\n"


def test_rejects_positional_only_parameters() -> None:
    """The fixer rejects signatures whose positional-only semantics would change."""
    with pytest.raises(FixRejectedError):
        fix_source(source="def apply(weight, bias, /):\n    pass\n")


def test_leaves_already_keyword_only_function_unchanged() -> None:
    """Already-compliant functions produce no change."""
    source = "def apply(*, weight, bias):\n    pass\n"

    result = fix_source(source=source)

    assert result.source == source
    assert result.status is FixStatus.UNCHANGED


def test_preserves_annotations_and_defaults() -> None:
    """The fixer changes only the parameter separator."""
    source = "def apply(weight: int, bias: int = 1) -> int:\n    return weight + bias\n"

    result = fix_source(source=source)

    assert result.source == "def apply(*, weight: int, bias: int = 1) -> int:\n    return weight + bias\n"


def test_preserves_decorators() -> None:
    """Decorators remain byte-for-byte unchanged."""
    source = "@decorator(option=True)\ndef apply(weight, bias):\n    pass\n"

    result = fix_source(source=source)

    assert result.source == "@decorator(option=True)\ndef apply(*, weight, bias):\n    pass\n"


@pytest.mark.parametrize("character", NON_PYTHON_LINE_BREAKS, ids=LINE_BREAK_IDS)
def test_does_not_treat_non_python_line_breaks_in_strings_as_lines(*, character: str) -> None:
    """A string character that splitlines treats as a break does not shift a later fix."""
    source = f"X = 'a{character}(b'\ndef apply(left, right):\n    return left\n"

    result = fix_source(source=source)

    assert result.source == f"X = 'a{character}(b'\ndef apply(*, left, right):\n    return left\n"


@pytest.mark.parametrize("character", [chr(0x2028), chr(0x0C)], ids=["line-separator", "form-feed"])
def test_handles_non_ascii_text_before_function(*, character: str) -> None:
    """A UTF-8 character before the string does not alter the insertion position."""
    source = f"é = 'a{character}(b'\n\ndef apply(left, right):\n    return left\n"

    result = fix_source(source=source)

    assert result.source == f"é = 'a{character}(b'\n\ndef apply(*, left, right):\n    return left\n"


def test_handles_non_python_line_break_in_crlf_source() -> None:
    """A non-Python line-break character does not change CRLF offset handling."""
    source = "X = 'a\u2028(b'\r\ndef apply(left, right):\r\n    return left\r\n"

    result = fix_source(source=source.encode())

    assert result.source == "X = 'a\u2028(b'\r\ndef apply(*, left, right):\r\n    return left\r\n".encode()


@pytest.mark.parametrize("character", NON_PYTHON_LINE_BREAKS, ids=LINE_BREAK_IDS)
def test_handles_every_non_python_line_break_with_byte_input(*, character: str) -> None:
    """Every non-Python line-break character is preserved in byte input."""
    source = f"X = 'a{character}(b'\ndef apply(left, right):\n    return left\n".encode()

    result = fix_source(source=source)

    assert result.source == f"X = 'a{character}(b'\ndef apply(*, left, right):\n    return left\n".encode()


def test_dry_run_preserves_affected_source() -> None:
    """Dry-run mode reports an affected source without changing it."""
    source = "X = 'a\u2028(b'\ndef apply(left, right):\n    return left\n"

    result = fix_source(source=source, dry_run=True)

    assert result.source == source
    assert result.status is FixStatus.WOULD_CHANGE


def test_handles_method_async_and_nested_functions() -> None:
    """Affected strings do not shift edits for methods, async functions or nested functions."""
    source = (
        "X = 'a\u2028(b'\n"
        "class Corrector:\n"
        "    def apply(self, left, right):\n"
        "        async def inner(first, second):\n"
        "            return first + second\n"
        "        return left + right\n"
    )

    result = fix_source(source=source)

    assert result.source == (
        "X = 'a\u2028(b'\n"
        "class Corrector:\n"
        "    def apply(self, *, left, right):\n"
        "        async def inner(*, first, second):\n"
        "            return first + second\n"
        "        return left + right\n"
    )


def test_handles_multiple_affected_strings_and_functions() -> None:
    """Multiple affected strings do not shift edits for multiple eligible functions."""
    source = (
        "X = 'a\u2028(b'\n"
        "Y = 'c\x0c(d'\n"
        "def first(left, right):\n"
        "    return left\n"
        "def second(first, second):\n"
        "    return second\n"
    ).encode()

    result = fix_source(source=source)

    assert (
        result.source
        == (
            "X = 'a\u2028(b'\n"
            "Y = 'c\x0c(d'\n"
            "def first(*, left, right):\n"
            "    return left\n"
            "def second(*, first, second):\n"
            "    return second\n"
        ).encode()
    )


@pytest.mark.parametrize("separator", ["/", "*args"], ids=["positional-only", "varargs"])
def test_preserves_negative_paths_with_affected_string(*, separator: str) -> None:
    """Affected strings do not change rejection or unchanged behaviour."""
    if separator == "/":
        source = "X = 'a\u2028(b'\ndef apply(left, right, /):\n    pass\n"
        with pytest.raises(FixRejectedError):
            fix_source(source=source)
    else:
        source = "X = 'a\u2028(b'\ndef apply(left, right, *args):\n    pass\n"
        result = fix_source(source=source)
        assert result.source == source
        assert result.status is FixStatus.UNCHANGED


def test_fixes_async_function() -> None:
    """Async functions use the same safe signature transformation."""
    source = "async def apply(weight, bias):\n    return weight + bias\n"

    result = fix_source(source=source)

    assert result.source == "async def apply(*, weight, bias):\n    return weight + bias\n"


def test_fixes_nested_functions() -> None:
    """Nested function definitions are included in the source edit."""
    source = (
        "def outer(first, second):\n    def inner(third, fourth):\n        return third + fourth\n    return inner\n"
    )

    result = fix_source(source=source)

    assert result.source == (
        "def outer(*, first, second):\n"
        "    def inner(*, third, fourth):\n"
        "        return third + fourth\n"
        "    return inner\n"
    )


def test_fixes_multiple_functions_in_one_source() -> None:
    """All eligible functions are fixed in one pass."""
    source = "def first(alpha, beta):\n    pass\n\ndef second(gamma, delta):\n    pass\n"

    result = fix_source(source=source)

    assert result.source == "def first(*, alpha, beta):\n    pass\n\ndef second(*, gamma, delta):\n    pass\n"


def test_preserves_utf8_bytes() -> None:
    """Byte input is returned as UTF-8 bytes without changing non-ASCII text."""
    source = "def apply(weight, bias):\n    return 'café'\n".encode()

    result = fix_source(source=source)

    assert result.source == "def apply(*, weight, bias):\n    return 'café'\n".encode()


def test_dry_run_preserves_bytes_and_reports_pending_change() -> None:
    """Dry-run mode preserves byte input while reporting a prospective edit."""
    source = b"def apply(weight, bias):\r\n    pass\r\n"

    result = fix_source(source=source, dry_run=True)

    assert result.source == source
    assert result.status is FixStatus.WOULD_CHANGE


def test_rejects_positional_only_parameters_even_with_annotations() -> None:
    """Positional-only syntax is rejected regardless of other signature details."""
    source = "def apply(weight: int, bias: int = 1, /) -> int:\n    return weight + bias\n"

    with pytest.raises(FixRejectedError, match="positional-only parameters in apply"):
        fix_source(source=source)


def test_rejects_positional_only_parameters_in_nested_function() -> None:
    """An unsafe nested signature rejects the complete source edit."""
    source = "def outer(first, second):\n    def inner(third, fourth, /):\n        pass\n    return inner\n"

    with pytest.raises(FixRejectedError):
        fix_source(source=source)


def test_varargs_function_is_unchanged() -> None:
    """A function with *args is left unchanged because insertion is not yet supported."""
    source = "def apply(weight, bias, *args):\n    pass\n"

    result = fix_source(source=source)

    assert result.source == source
    assert result.status is FixStatus.UNCHANGED


def test_rejects_signature_when_opening_parenthesis_cannot_be_located() -> None:
    """The fixer rejects an unsupported AST-to-source mapping."""

    class UnfindableOpening(str):
        """Source whose opening-parenthesis lookup fails."""

        __slots__ = ()

        # noinspection PyTypeHints
        def find(
            self, sub: str, start: SupportsIndex | None = None, end: SupportsIndex | None = None
        ) -> int:  # pyrigor PYR402 # mirrors str.find for the test double
            """Make the opening-parenthesis lookup fail."""
            if sub == "(":
                return -1
            return super().find(sub, start, end)

    with pytest.raises(FixRejectedError, match="unsupported signature in apply"):
        fix_source(source=UnfindableOpening("def apply(weight, bias):\n    pass\n"))


def test_rejects_method_when_comma_cannot_be_located() -> None:
    """The fixer rejects a method when its self-separator cannot be located."""

    class UnfindableComma(str):
        """Source whose comma lookup fails after finding the opening parenthesis."""

        __slots__ = ()

        # noinspection PyTypeHints
        def find(
            self, sub: str, start: SupportsIndex | None = None, end: SupportsIndex | None = None
        ) -> int:  # pyrigor PYR402 # mirrors str.find for the test double
            """Make the comma lookup fail."""
            if sub == ",":
                return -1
            return super().find(sub, start, end)

    source = UnfindableComma("class Corrector:\n    def apply(self, weight, bias):\n        pass\n")

    with pytest.raises(FixRejectedError, match="unsupported signature in apply"):
        fix_source(source=source)
