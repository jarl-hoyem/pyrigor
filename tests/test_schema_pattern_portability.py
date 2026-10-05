"""Keep the v2 schema's patterns inside the subset that every regular expression engine reads alike.

JSON Schema patterns are meant to be ECMAScript, but each validator hands them to its own engine. Python, ECMAScript
and the RE2-based engines of Go and Rust agree on character classes, quantifiers, groups, alternation and anchors. The
schema therefore stays within those.
"""

import json
import re
from typing import Any

import pytest

from tests.diagnostics_v2_support import Json, load_v2_schema

_BACKSLASH = chr(0x5C)
_ESCAPE = "escape"
_GROUP = "group"
_PATTERN = "pattern"
_PATTERN_PROPERTIES = "patternProperties"
# Whatever each engine counts as whitespace, this class matches every character in all of them.
_ANY_CHARACTER = f"[{_BACKSLASH}s{_BACKSLASH}S]"
_TOKEN = re.compile(
    f"(?P<any>{re.escape(_ANY_CHARACTER)})"  # first, so that it wins over the two shorthands inside it
    f"|(?P<escape>{re.escape(_BACKSLASH)}.)"  # taken whole, so that an escaped backslash hides what follows it
    "|(?P<group>[(][?](?:[=!]|<[=!]|<|P|[a-zA-Z]))"  # a lookaround, a named group or an inline flag
    "|.",
    re.DOTALL,
)
_ESCAPE_KINDS = {
    "character shorthand": "sSdDwW",
    "word boundary": "bB",
    "backreference": "123456789k",
    "Unicode property": "pP",
}
_LOOKAROUND_OPENERS = ("(?=", "(?!", "(?<=", "(?<!")
_LOOKAROUND = "lookaround group"
_GROUP_OR_FLAG = "named group or inline flag"
_SHORTHAND = "character shorthand"
_FLAGGED = [
    ("^(?!a)", {_LOOKAROUND}),
    ("a(?=b)", {_LOOKAROUND}),
    ("(?<=a)b", {_LOOKAROUND}),
    ("(?<!a)b", {_LOOKAROUND}),
    (f"(a){_BACKSLASH}1", {"backreference"}),
    (f"(?<n>a){_BACKSLASH}k<n>", {"backreference", _GROUP_OR_FLAG}),
    (f"{_BACKSLASH}d+", {_SHORTHAND}),
    (f"{_BACKSLASH}w", {_SHORTHAND}),
    (f"[{_BACKSLASH}sa]", {_SHORTHAND}),
    (f"{_BACKSLASH}bword", {"word boundary"}),
    (f"{_BACKSLASH}p{{L}}", {"Unicode property"}),
    ("(?P<n>a)", {_GROUP_OR_FLAG}),
    ("(?i)a", {_GROUP_OR_FLAG}),
    (f"{_BACKSLASH}[{_BACKSLASH}s{_BACKSLASH}S]", {_SHORTHAND}),  # an escaped bracket, so not the any-character class
    (f"{_BACKSLASH * 3}s", {_SHORTHAND}),  # an escaped backslash, then real shorthand
]
_ACCEPTED = [
    "^[^.<>]+$",
    "^(?:a|b)*$",
    f"^{_ANY_CHARACTER}*$",
    f"{_BACKSLASH * 2}s",  # an escaped backslash, then the letter s
    f"[{_BACKSLASH}t{_BACKSLASH}n{_BACKSLASH}x0b{_BACKSLASH}u00a0]",
]


def _escape_kinds(*, token: str) -> set[str]:
    """Name the construct an escape stands for, when engines read it differently."""
    return {kind for kind, letters in _ESCAPE_KINDS.items() if token[1] in letters}


def _group_kind(*, token: str) -> str:
    """Name the kind of group that opens with a question mark."""
    return _LOOKAROUND if token.startswith(_LOOKAROUND_OPENERS) else _GROUP_OR_FLAG


def forbidden_constructs(*, pattern: str) -> set[str]:
    """Name each construct of the pattern that engines read differently, allowing the any-character class."""
    found: set[str] = set()
    for match in _TOKEN.finditer(pattern):
        if match.lastgroup == _ESCAPE:
            found |= _escape_kinds(token=match.group())
        elif match.lastgroup == _GROUP:
            found.add(_group_kind(token=match.group()))
    return found


def _object_patterns(*, pairs: list[tuple[str, Any]]) -> list[str]:
    """List the patterns one JSON object carries, and the keys of its patternProperties."""
    found: list[str] = []
    for key, value in pairs:
        if key == _PATTERN and isinstance(value, str):
            found.append(value)
        elif key == _PATTERN_PROPERTIES:
            found.extend(value)
    return found


def _record_patterns(*, found: list[str], pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Add the patterns one JSON object carries to the list and hand the object back as the parser expects."""
    found.extend(_object_patterns(pairs=pairs))
    return dict(pairs)


def patterns_in(*, schema: Json) -> list[str]:
    """List every pattern of a schema, and every key of a patternProperties object, wherever they stand.

    The JSON parser hands each object to this function, so it finds them without walking the schema itself. The
    check-in scripts/check_schema_pattern_portability.py walks the schema by hand, and the two are independent of
    each other.
    """
    found: list[str] = []
    json.loads(json.dumps(schema), object_pairs_hook=lambda pairs: _record_patterns(found=found, pairs=pairs))
    return found


def offending_patterns(*, schema: Json) -> dict[str, list[str]]:
    """Map each pattern that uses a forbidden construct to the constructs it uses."""
    constructs = {pattern: forbidden_constructs(pattern=pattern) for pattern in patterns_in(schema=schema)}
    return {pattern: sorted(found) for pattern, found in constructs.items() if found}


def test_every_pattern_of_the_schema_uses_only_portable_constructs() -> None:
    """No pattern of the schema uses a construct that Python, ECMAScript and RE2-based engines read differently."""
    offenders = offending_patterns(schema=load_v2_schema())
    assert not offenders


@pytest.mark.parametrize(("pattern", "expected"), _FLAGGED)
def test_the_scan_flags_each_forbidden_construct(*, pattern: str, expected: set[str]) -> None:
    """Each construct the engines disagree on is named, including one that only follows an escaped backslash."""
    assert forbidden_constructs(pattern=pattern) == expected


@pytest.mark.parametrize("pattern", _ACCEPTED)
def test_the_scan_accepts_the_portable_subset(*, pattern: str) -> None:
    """Classes, groups, alternation, escapes of one character and the any-character class are not flagged."""
    assert forbidden_constructs(pattern=pattern) == set()


def test_the_scan_finds_a_pattern_wherever_the_schema_keeps_one() -> None:
    """A pattern is found at the top, in a definition, under a keyword and as a patternProperties key."""
    schema = {
        "pattern": "^a$",
        "$defs": {"Name": {"allOf": [{"type": "string"}, {"pattern": "^b$"}]}},
        "properties": {"pattern": {"type": "string"}, "code": {"pattern": "^c$"}},
        "patternProperties": {"^d$": {"type": "string"}},
        "items": {"if": {"pattern": "^e$"}, "then": {"not": {"pattern": "^f$"}}},
    }
    assert sorted(patterns_in(schema=schema)) == ["^a$", "^b$", "^c$", "^d$", "^e$", "^f$"]


def test_a_lookahead_added_to_the_schema_is_reported() -> None:
    """The scan of the real schema fails when a lookahead comes back."""
    schema = load_v2_schema()
    schema["$defs"]["FileName"]["allOf"].append({"description": "A lookahead.", "pattern": "^(?!a)"})
    assert offending_patterns(schema=schema) == {"^(?!a)": [_LOOKAROUND]}
