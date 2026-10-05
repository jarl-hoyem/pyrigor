"""Compare the symbol name grammar of the v2 schema with the EnclosingSymbol type over every short name.

The schema states the grammar in patterns and the type enforces it in code. Agreement of Python and Node on each
pattern shows that the patterns read alike, not that they accept the right names. So these tests compare the schema
with the type and with the placement rules, which they state on their own. A name is built from up to three segments
joined by dots, so every combination of empty, odd and special segments is tried. Two relations are pinned:

- On ASCII names the schema accepts a name for a kind exactly when the type accepts it and the kind's placement rule
  holds. A function stands alone or inside a function, a method stands directly in a class, a module is `<module>`
  and a class has no placement rule.
- Beyond ASCII the schema checks loosely, because a pattern cannot carry Unicode categories portably. It is looser
  than the type there and only there, and it never rejects a name the type accepts.
"""

import functools
import itertools
from collections.abc import Callable

import pytest
from jsonschema.protocols import Validator

from pyrigor.findings import EnclosingSymbol, SymbolKind
from tests.diagnostics_v2_support import definition_validator

_LOCALS = "<locals>"
_MODULE = "<module>"
_ASCII_SEGMENTS = ("a", "_a", "1", "a b", "<", "", _LOCALS, _MODULE)
_NON_ASCII_SEGMENTS = ("a", chr(0xE9), chr(0x660), chr(0xA7), chr(0x1D400), "1", "")
_MOST_SEGMENTS = 3
_ASCII_LIMIT = 0x7F
# What each kind requires of the segments of its name, stated here and not read from the schema or the type.
_PLACEMENT: dict[SymbolKind, Callable[[list[str]], bool]] = {
    SymbolKind.MODULE: lambda segments: segments == [_MODULE],
    SymbolKind.FUNCTION: lambda segments: len(segments) == 1 or segments[-2] == _LOCALS,
    SymbolKind.METHOD: lambda segments: len(segments) > 1 and segments[-2] != _LOCALS,
    SymbolKind.CLASS: lambda _segments: True,
}


@functools.cache
def _schema() -> Validator:
    """Build the validator for the enclosing symbol, once."""
    return definition_validator(definition="EnclosingSymbol")


def _names(*, segments: tuple[str, ...]) -> list[str]:
    """List every name made of one of the most segments, joined by dots."""
    return [
        ".".join(chosen)
        for length in range(1, _MOST_SEGMENTS + 1)
        for chosen in itertools.product(segments, repeat=length)
    ]


def _schema_accepts(*, kind: SymbolKind, name: str) -> bool:
    """Tell whether the schema accepts the name for the kind."""
    return _schema().is_valid({"kind": kind.value, "name": name})


def _producer_accepts(*, kind: SymbolKind, name: str) -> bool:
    """Tell whether the type accepts the name for the kind."""
    try:
        EnclosingSymbol(kind=kind, name=name)
    except ValueError:
        return False
    return True


def _expected(*, kind: SymbolKind, name: str) -> bool:
    """Tell whether the type accepts the name and the placement rule of the kind holds."""
    return _producer_accepts(kind=kind, name=name) and _PLACEMENT[kind](name.split("."))


def _accepted_by(*, first: Callable[..., bool], but_not: Callable[..., bool], names: list[str]) -> list[str]:
    """List the class names that the first judge accepts and the second rejects."""
    kind = SymbolKind.CLASS
    return [name for name in names if first(kind=kind, name=name) and not but_not(kind=kind, name=name)]


def _has_non_ascii(*, name: str) -> bool:
    """Tell whether the name holds a character beyond ASCII."""
    return any(ord(character) > _ASCII_LIMIT for character in name)


@pytest.mark.parametrize("line_feeds", [1, 2, 3])
@pytest.mark.parametrize(
    ("kind", "name"),
    [
        pytest.param(SymbolKind.FUNCTION, "apply", id="function"),
        pytest.param(SymbolKind.METHOD, "Report.render", id="method"),
        pytest.param(SymbolKind.CLASS, "Report", id="class"),
    ],
)
def test_a_name_with_final_line_feeds_is_rejected(*, kind: SymbolKind, name: str, line_feeds: int) -> None:
    """The patterns accept any run of final line feeds in both engines, so the control character rule rejects it."""
    assert not _schema_accepts(kind=kind, name=name + "\n" * line_feeds)


@pytest.mark.parametrize("kind", [pytest.param(kind, id=kind.value) for kind in SymbolKind])
def test_the_schema_accepts_an_ascii_name_exactly_when_the_type_and_the_placement_rule_do(*, kind: SymbolKind) -> None:
    """The schema is neither stricter nor looser than the type and the placement rule of the kind."""
    names = _names(segments=_ASCII_SEGMENTS)
    disagreeing = [name for name in names if _schema_accepts(kind=kind, name=name) != _expected(kind=kind, name=name)]
    assert not disagreeing


def test_the_schema_is_looser_than_the_type_only_beyond_ascii() -> None:
    """The type accepts nothing the schema rejects, and the schema accepts more only through non-ASCII characters."""
    names = _names(segments=_NON_ASCII_SEGMENTS)
    only_in_the_type = _accepted_by(first=_producer_accepts, but_not=_schema_accepts, names=names)
    only_in_the_schema = _accepted_by(first=_schema_accepts, but_not=_producer_accepts, names=names)
    assert not only_in_the_type
    assert only_in_the_schema
    assert all(_has_non_ascii(name=name) for name in only_in_the_schema)
