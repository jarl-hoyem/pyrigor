"""Tests for escape sequences in the v2 schema's enclosing symbol names and messages.

A character the invisible-text rule rejects is written as an escape because Python accepts a few such characters in
identifiers. The schema checks the shape of an escape and leaves the rest to the producer.
"""

from typing import cast

import pytest

from tests.diagnostics_v2_support import Json, definition_validator, load_v2_schema

_BACKSLASH = chr(0x5C)
_RANGE_INVARIANT = "stands for that code point up to U+10FFFF"
_NAME = "name"
_MESSAGE = "message"
# Valid inside a Python identifier and rejected by the invisible-text rule. U+200C and U+200D need Python 3.13 or later.
_IDENTIFIER_CODE_POINTS = [
    pytest.param(code_point, id=f"U+{code_point:04X}") for code_point in (0x200C, 0x200D, 0x034F, 0x115F, 0x1160)
]


def _is_valid_symbol(*, kind: str, name: str) -> bool:
    """Return whether an enclosing symbol validates against the schema."""
    symbol: Json = {"kind": kind, "name": name}
    return definition_validator(definition="EnclosingSymbol").is_valid(symbol)


@pytest.mark.parametrize(
    ("kind", "name"),
    [
        pytest.param("function", f"a{_BACKSLASH}u200cb", id="zero-width-non-joiner"),
        pytest.param("method", f"Report.a{_BACKSLASH}u034fb", id="grapheme-joiner-in-a-method"),
        pytest.param("function", f"a{_BACKSLASH}U0001f600b", id="character-above-the-basic-plane"),
        pytest.param("function", f"{_BACKSLASH}u200ca", id="escape-at-the-start-of-a-segment"),
        pytest.param("function", f"outer.<locals>.a{_BACKSLASH}u200cb", id="nested-function"),
        pytest.param("class", f"Outer.In{_BACKSLASH}u200cner", id="nested-class"),
        pytest.param("function", f"a{_BACKSLASH}U0010ffffb", id="highest-code-point"),
        pytest.param("function", f"a{_BACKSLASH}u200c{_BACKSLASH}u034f", id="two-escapes-in-a-row"),
    ],
)
def test_escape_in_a_symbol_name_is_accepted(*, kind: str, name: str) -> None:
    """An escape for one code point is accepted inside a segment, alone and in a qualified name."""
    assert _is_valid_symbol(kind=kind, name=name)


@pytest.mark.parametrize(
    "name",
    [
        pytest.param(f"a{_BACKSLASH}x41", id="hexadecimal-escape-form"),
        pytest.param(f"a{_BACKSLASH}u20", id="two-digits"),
        pytest.param(f"a{_BACKSLASH}u200", id="three-digits"),
        pytest.param(f"a{_BACKSLASH}u200g", id="non-hexadecimal-digit"),
        pytest.param(f"a{_BACKSLASH}u200C", id="uppercase-digit"),
        pytest.param(f"a{_BACKSLASH}U0001F600", id="long-escape-with-uppercase-digits"),
        pytest.param(f"a{_BACKSLASH}U0001f60", id="long-escape-with-seven-digits"),
        pytest.param(f"a{_BACKSLASH}", id="trailing-backslash"),
        pytest.param(f"a{_BACKSLASH}{_BACKSLASH}b", id="doubled-backslash"),
        pytest.param(f"a{_BACKSLASH}nb", id="backslash-before-another-letter"),
        pytest.param(f"a{_BACKSLASH}u 200c", id="space-inside-an-escape"),
    ],
)
def test_malformed_escape_in_a_symbol_name_is_rejected(*, name: str) -> None:
    """Only a backslash, u and four lowercase digits, or a backslash, U and eight, is an escape."""
    assert not _is_valid_symbol(kind="function", name=name)


def test_escape_range_is_left_to_the_producer() -> None:
    """The schema checks the shape of an escape, not its range, and x-invariants record the range for the producer."""
    invariants = " ".join(cast("list[str]", load_v2_schema()["x-invariants"]))

    assert _is_valid_symbol(kind="function", name=f"a{_BACKSLASH}U00110000")
    assert _RANGE_INVARIANT in invariants


def test_escape_only_segment_is_left_to_the_producer() -> None:
    """A segment made of one escape can decode to a character that cannot start an identifier.

    The schema cannot tell, so the producer must not write such a name.
    """
    assert _is_valid_symbol(kind="function", name=f"{_BACKSLASH}u200c")


@pytest.mark.parametrize(
    ("kind", "name"),
    [
        pytest.param("method", f"a{_BACKSLASH}u200cb", id="method-without-a-class"),
        pytest.param("function", f"Report.a{_BACKSLASH}u200cb", id="function-directly-in-a-class"),
        pytest.param("module", f"a{_BACKSLASH}u200cb", id="module-kind-with-an-escaped-name"),
        pytest.param("function", f"9{_BACKSLASH}u200cb", id="segment-starting-with-a-digit"),
        pytest.param("function", f"a{_BACKSLASH}u200c{chr(10)}", id="trailing-newline"),
        pytest.param("function", f"a{_BACKSLASH}u{chr(0x662) * 3}c", id="arabic-indic-digits-in-an-escape"),
        pytest.param("function", f"a{_BACKSLASH}u{chr(0xFF12)}00c", id="fullwidth-digit-in-an-escape"),
    ],
)
def test_escape_does_not_bypass_the_other_symbol_rules(*, kind: str, name: str) -> None:
    """The kind rules, the identifier shape and the control-character rule still apply to a name with an escape."""
    assert not _is_valid_symbol(kind=kind, name=name)


def _finding_carrying(*, field: str, text: str) -> Json:
    """Build a finding that carries the text inside a symbol name or inside its message."""
    carried = f"a{text}b"
    span = {
        "file_name": "a.py",
        "byte_start": 0,
        "byte_end": 1,
        "line_start": 1,
        "column_start": 1,
        "line_end": 1,
        "column_end": 2,
        "is_primary": True,
    }
    return {
        "code": "PYR402",
        "message": f"Function {carried} has positional parameters" if field == _MESSAGE else "Function apply is bad",
        "level": "warning",
        "spans": [span],
        "fixes": [],
        "enclosing_symbol": {"kind": "function", "name": carried if field == _NAME else "apply"},
    }


@pytest.mark.parametrize("field", [_NAME, _MESSAGE])
@pytest.mark.parametrize("code_point", _IDENTIFIER_CODE_POINTS)
def test_raw_identifier_character_is_still_rejected(*, code_point: int, field: str) -> None:
    """Allowing escapes does not loosen the invisible-text rule: the raw character stays rejected."""
    finding = _finding_carrying(field=field, text=chr(code_point))

    assert not definition_validator(definition="Finding").is_valid(finding)


@pytest.mark.parametrize("field", [_NAME, _MESSAGE])
@pytest.mark.parametrize("code_point", _IDENTIFIER_CODE_POINTS)
def test_escaped_identifier_character_is_accepted(*, code_point: int, field: str) -> None:
    """The escape is how a name or a message carries a character Python allows in an identifier."""
    finding = _finding_carrying(field=field, text=f"{_BACKSLASH}u{code_point:04x}")

    assert definition_validator(definition="Finding").is_valid(finding)
