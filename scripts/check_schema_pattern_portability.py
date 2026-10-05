"""Check that every pattern of a JSON Schema matches the same strings in Python and in Node.

JSON Schema patterns are meant to be ECMAScript, but each validator hands them to its own engine. The v2 diagnostics
schema is a contract for consumers written in other languages, so a pattern that Python and ECMAScript read
differently is a defect in the contract. This script asks Node and Python the same question about every pattern and a
large corpus of hostile and boundary strings. Any disagreement makes the run fail. Node is asked twice, without and
with the Unicode flag, because ajv, the most common JavaScript validator, compiles every pattern with it.

The corpus has two parts. Every string of up to three characters over a fixed hostile alphabet covers the traps the
engines are known to disagree on. Each code point the patterns themselves name, with its two neighbours, is placed in
a few templates, so a range added to the schema is probed without a change here.
"""

import json
import re
import subprocess  # nosec B404 -- runs node to read the schema's patterns
import sys
from collections.abc import Iterable
from itertools import product
from pathlib import Path
from typing import Any, NamedTuple

from dev_tooling_shared import find_executable

DEFAULT_SCHEMA = Path(__file__).parent.parent / "schemas" / "pyrigor-diagnostics-v2.json"

# Every shape a parsed JSON value can have. The members of an object or array are Any, which is what the standard
# library's own stubs use, and naming the shapes lets a type checker narrow a value without a cast.
_JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None

_BACKSLASH = chr(0x5C)
_PATTERN = "pattern"
_PATTERN_PROPERTIES = "patternProperties"
_MAX_ALPHABET_STRING_LENGTH = 3
_ASCII_LIMIT = 0x7F
_MAX_CODE_POINT = 0x10FFFF
_SURROGATES = range(0xD800, 0xE000)
_MAX_REPORTED = 10  # disagreements named per pattern, so one bad pattern does not bury the others
_USAGE_ERROR = 2

# The traps the engines are known to disagree on, one character each: a line feed for `$`, the separators and
# controls for `\s` and `.`, a decimal digit outside ASCII for `\d` and characters outside the Basic Multilingual
# Plane.
_HOSTILE_ALPHABET = (
    "a",
    "0",
    " ",
    ":",
    "/",
    _BACKSLASH,
    ".",
    "<",
    ">",
    "\n",
    chr(0x1C),
    chr(0x85),
    chr(0xA0),
    chr(0x2028),
    chr(0x2029),
    chr(0xFEFF),
    chr(0x660),
    chr(0x34F),
    chr(0x1D400),
    chr(0x20000),
    chr(0xE0001),
)
# Edges of the encodings that no pattern needs to name for them to matter.
_EXTRA_CODE_POINTS = (0x7F, 0x80, 0xFF, 0x100, 0xFFFF, 0x10000, _MAX_CODE_POINT)
_TEMPLATES = ("{}", "a{}", "{}a", "a{}a", "a/{}", "{}.py", "a.{}")
_ESCAPED_CODE_POINT = re.compile(f"{re.escape(_BACKSLASH)}(?:x(?P<byte>[0-9a-fA-F]{{2}})|u(?P<unit>[0-9a-fA-F]{{4}}))")

# Node reads every pattern twice. Without flags is what the JSON Schema specification describes. With the Unicode flag
# is what ajv, the most common JavaScript validator, does by default. The flag changes how syntax and astral characters
# read.
_NODE_FLAG_SETS = ("", "u")

# The data arrives as a JSON literal ahead of this text, which reads the patterns with the flags it names and answers
# with the indexes of the strings that each one matches. JSON is a subset of JavaScript, so no argument or file carries
# the data.
_NODE_SCRIPT = """
const results = {};
for (const [pointer, pattern] of Object.entries(input.patterns)) {
  let expression;
  try {
    expression = new RegExp(pattern, input.flags);
  } catch (error) {
    results[pointer] = { error: String(error) };
    continue;
  }
  const matching = [];
  input.strings.forEach((text, index) => {
    if (expression.test(text)) {
      matching.push(index);
    }
  });
  results[pointer] = { matching };
}
process.stdout.write(JSON.stringify(results));
"""


class NodeError(RuntimeError):
    """Node failed, or its answer is one this script cannot read."""


class Verdict(NamedTuple):
    """What one engine made of one pattern: the indexes of the strings it matches, or why it cannot read it."""

    matching: frozenset[int]
    error: str | None


class Report(NamedTuple):
    """The problems found in a schema, with the size of the check that found them."""

    problems: list[str]
    pattern_count: int
    string_count: int


class _Member(NamedTuple):
    """A member of a JSON object or array, with the JSON pointer that leads to it."""

    pointer: str
    value: _JsonValue


def _members(*, node: _JsonValue, pointer: str) -> list[_Member]:
    """List the members of a JSON object or array, and none for any other value."""
    if isinstance(node, dict):
        return [_Member(pointer=f"{pointer}/{key}", value=value) for key, value in node.items()]
    if isinstance(node, list):
        return [_Member(pointer=f"{pointer}/{index}", value=value) for index, value in enumerate(node)]
    return []


def _own_patterns(*, node: _JsonValue, pointer: str) -> dict[str, str]:
    """Map the JSON pointer of the patterns a schema node carries itself to their expressions."""
    if not isinstance(node, dict):
        return {}
    found: dict[str, str] = {}
    pattern = node.get(_PATTERN)
    if isinstance(pattern, str):
        found[f"{pointer}/{_PATTERN}"] = pattern
    for expression in node.get(_PATTERN_PROPERTIES, {}):
        found[f"{pointer}/{_PATTERN_PROPERTIES}/{expression}"] = expression
    return found


def collect_patterns(*, node: _JsonValue, pointer: str = "") -> dict[str, str]:
    """Map the JSON pointer of every pattern in a schema node, and of every patternProperties key, to its expression."""
    found = _own_patterns(node=node, pointer=pointer)
    for member in _members(node=node, pointer=pointer):
        found.update(collect_patterns(node=member.value, pointer=member.pointer))
    return found


def _escaped_code_points(*, pattern: str) -> set[int]:
    """List the code points a pattern names with an escape."""
    return {int(escape["byte"] or escape["unit"], 16) for escape in _ESCAPED_CODE_POINT.finditer(pattern)}


def _literal_code_points(*, pattern: str) -> set[int]:
    """List the code points a pattern spells as a literal character beyond ASCII."""
    return {ord(character) for character in pattern if ord(character) > _ASCII_LIMIT}


def _named_code_points(*, patterns: Iterable[str]) -> set[int]:
    """List the code points that the patterns name, by escape or as a literal character beyond ASCII."""
    points: set[int] = set()
    for pattern in patterns:
        points |= _escaped_code_points(pattern=pattern) | _literal_code_points(pattern=pattern)
    return points


def _alphabet_strings() -> set[str]:
    """List every string of up to a few characters over the hostile alphabet."""
    return {
        "".join(combination)
        for length in range(_MAX_ALPHABET_STRING_LENGTH + 1)
        for combination in product(_HOSTILE_ALPHABET, repeat=length)
    }


def _is_character(*, code_point: int) -> bool:
    """Tell whether a code point is a character a string can hold, which excludes the surrogates."""
    return 0 <= code_point <= _MAX_CODE_POINT and code_point not in _SURROGATES


def _with_neighbours(*, code_points: set[int]) -> set[int]:
    """Add the code point before and the one after each of the code points."""
    return {code_point + step for code_point in code_points for step in (-1, 0, 1)}


def _nearby_characters(*, patterns: Iterable[str]) -> list[str]:
    """List the characters at, just before and just after each code point that the patterns name."""
    named = _named_code_points(patterns=patterns) | set(_EXTRA_CODE_POINTS)
    return [
        chr(code_point) for code_point in _with_neighbours(code_points=named) if _is_character(code_point=code_point)
    ]


def _boundary_strings(*, patterns: Iterable[str]) -> set[str]:
    """Place each character near a code point that the patterns name in a few templates."""
    return {
        template.format(character) for character in _nearby_characters(patterns=patterns) for template in _TEMPLATES
    }


def build_corpus(*, patterns: Iterable[str]) -> list[str]:
    """Build the strings to ask both engines about, in a fixed order."""
    strings = _alphabet_strings() | _boundary_strings(patterns=patterns)
    # Python's `$` also matches before a final line feed and ECMAScript's does not, so every string is tried with one.
    strings |= {text + "\n" for text in strings}
    return sorted(strings, key=lambda text: (len(text), text))


def _python_verdict(*, pattern: str, strings: list[str]) -> Verdict:
    """Ask Python's re module, which is what JSON Schema validators in Python use, about every string."""
    try:
        expression = re.compile(pattern)
    except re.error as error:
        return Verdict(matching=frozenset(), error=str(error))
    return Verdict(
        matching=frozenset(index for index, text in enumerate(strings) if expression.search(text)),
        error=None,
    )


def _run_node(*, node: str, patterns: dict[str, str], strings: list[str], flags: str) -> str:
    """Run Node once on every pattern and string with the given flags and return what it printed."""
    # The default escapes every non-ASCII character, so the text is the same on every console and in every encoding.
    data = json.dumps({"patterns": patterns, "strings": strings, "flags": flags})
    result = subprocess.run(  # nosec B603 # noqa: S603 -- node from shutil.which, fixed script, no untrusted input
        [node, "-"],
        input=f"const input = {data};\n{_NODE_SCRIPT}",
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout


def _node_output(*, node: str, patterns: dict[str, str], strings: list[str], flags: str) -> str:
    """Run Node, reporting a failed run as a NodeError."""
    try:
        return _run_node(node=node, patterns=patterns, strings=strings, flags=flags)
    except subprocess.CalledProcessError as error:
        raise NodeError(f"node exited with code {error.returncode}: {error.stderr.strip()}") from error


def _parse_answers(*, output: str) -> dict[str, Verdict]:
    """Read Node's answers, which map each pattern to the strings it matches or to why it cannot read it."""
    try:
        answers: dict[str, dict[str, Any]] = json.loads(output)
    except json.JSONDecodeError as error:
        raise NodeError(f"node answered with text that is not JSON: {error}") from error
    return {
        pointer: Verdict(matching=frozenset(answer.get("matching", [])), error=answer.get("error"))
        for pointer, answer in answers.items()
    }


def _node_verdicts(*, node: str, patterns: dict[str, str], strings: list[str], flags: str) -> dict[str, Verdict]:
    """Ask Node about every pattern and string with one run."""
    return _parse_answers(output=_node_output(node=node, patterns=patterns, strings=strings, flags=flags))


def _node_name(*, flags: str) -> str:
    """Name Node as it was run, so a report says whether the Unicode flag was set."""
    return f"Node with the {flags} flag" if flags else "Node"


def _unreadable(*, pointer: str, python: Verdict, node: Verdict, node_name: str) -> list[str]:
    """Name each engine that cannot read the pattern."""
    return [
        f"{pointer}: {engine} cannot read the pattern: {verdict.error}"
        for engine, verdict in (("Python", python), (node_name, node))
        if verdict.error is not None
    ]


def _differences(*, pointer: str, python: Verdict, node: Verdict, strings: list[str], node_name: str) -> list[str]:
    """Name the first strings that only one engine matches and count the rest."""
    differing = sorted(python.matching ^ node.matching)
    problems = [
        f"{pointer}: {'Python' if index in python.matching else node_name} matches {strings[index]!a}"
        " and the other engine does not"
        for index in differing[:_MAX_REPORTED]
    ]
    if len(differing) > _MAX_REPORTED:
        problems.append(f"{pointer}: and {len(differing) - _MAX_REPORTED} more strings")
    return problems


def _disagreements(*, pointer: str, python: Verdict, node: Verdict, strings: list[str], node_name: str) -> list[str]:
    """Describe how Python and Node read one pattern differently or return nothing when they agree."""
    return _unreadable(pointer=pointer, python=python, node=node, node_name=node_name) or _differences(
        pointer=pointer, python=python, node=node, strings=strings, node_name=node_name
    )


def _python_verdicts(*, patterns: dict[str, str], strings: list[str]) -> dict[str, Verdict]:
    """Ask Python about every pattern and string."""
    return {pointer: _python_verdict(pattern=pattern, strings=strings) for pointer, pattern in patterns.items()}


def _problems_for_flags(
    *, node: str, flags: str, patterns: dict[str, str], strings: list[str], python: dict[str, Verdict]
) -> list[str]:
    """Compare Python with Node run under the given flags."""
    node_verdicts = _node_verdicts(node=node, patterns=patterns, strings=strings, flags=flags)
    problems: list[str] = []
    for pointer in patterns:
        problems += _disagreements(
            pointer=pointer,
            python=python[pointer],
            node=node_verdicts[pointer],
            strings=strings,
            node_name=_node_name(flags=flags),
        )
    return problems


def check_schema(*, schema_path: Path, node: str) -> Report:
    """Compare Python and Node, run without and with the Unicode flag, on every pattern of the schema file."""
    patterns = collect_patterns(node=json.loads(schema_path.read_text(encoding="utf-8")))
    if not patterns:
        return Report(problems=["no pattern found, so nothing was checked"], pattern_count=0, string_count=0)
    strings = build_corpus(patterns=patterns.values())
    python = _python_verdicts(patterns=patterns, strings=strings)
    problems = [
        problem
        for flags in _NODE_FLAG_SETS
        for problem in _problems_for_flags(node=node, flags=flags, patterns=patterns, strings=strings, python=python)
    ]
    return Report(problems=problems, pattern_count=len(patterns), string_count=len(strings))


def _print_report(*, report: Report) -> int:
    """Print what the check found and return the exit code for it."""
    if report.problems:
        print(*report.problems, sep="\n")
        return 1
    print(
        f"{report.pattern_count} patterns match alike in Python and Node on {report.string_count} strings,"
        " with and without the u flag."
    )
    return 0


def _run_check(*, schema_path: Path, node: str) -> int:
    """Check one schema file and print the result, treating a file or Node that cannot be read as a failure."""
    try:
        report = check_schema(schema_path=schema_path, node=node)
    except (OSError, json.JSONDecodeError, NodeError) as error:
        print(f"{schema_path}: {error}")
        return 1
    return _print_report(report=report)


def main() -> int:
    """Check the schema named on the command line, or the v2 diagnostics schema."""
    arguments = sys.argv[1:]
    if len(arguments) > 1:
        print("usage: check_schema_pattern_portability.py [SCHEMA]", file=sys.stderr)
        return _USAGE_ERROR
    schema_path = Path(arguments[0]) if arguments else DEFAULT_SCHEMA
    return _run_check(schema_path=schema_path, node=find_executable(name="node"))


if __name__ == "__main__":
    raise SystemExit(main())
