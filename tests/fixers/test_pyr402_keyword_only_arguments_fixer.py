"""Tests for the opt-in PYR402 fixer."""
# pylint: disable=magic-value-comparison

from typing import SupportsIndex

import pytest

from pyrigor.fixers.pyr402_keyword_only_arguments_fixer import FixRejectedError, FixStatus, fix_source


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
