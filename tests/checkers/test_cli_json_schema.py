"""JSON schema validation tests for pyrigor's CLI output."""

import ast
import json
import sys
import tokenize
from io import BytesIO, StringIO, TextIOWrapper
from os.path import relpath
from pathlib import Path
from typing import NamedTuple, cast
from unittest.mock import patch

import jsonschema
import pytest

from pyrigor.checkers import CHECKERS

# noinspection PyProtectedMember
from pyrigor.checkers.cli import main, run  # pyright: ignore[reportPrivateUsage]
from pyrigor.findings import FileName, PositionIndex, make_span
from pyrigor.rules import Rule
from tests.line_breaks import LINE_BREAK_IDS, NON_PYTHON_LINE_BREAKS

# Pytest injects the schema fixture into each test.
# pylint: disable=redefined-outer-name

_SCHEMA_VERSION = 2
_TOOL_NAME = "pyrigor"
_APPLICABILITY = "applicability"
_MALFORMED_SUPPRESSION = "malformed_suppression"
_WARNING_PREFIX = "Warning:"
_ESCAPED_NON_ASCII_PREFIX = "\\u00e9"
_ESCAPED_ASTRAL_PREFIX = "\\ud801"
_NORMALISED_HEADER_SOURCE = "def \u212a(self, a, b):"
_READ_ERROR = "read_error"
_NO_FIXES = "none"
_NON_ASCII_NAME = "gr\u00f6\u00dfe"
_ESCAPED_NON_ASCII = "\\u00f6"
_SHIFTED_LINE_SOURCE = "X = 'a{character}b'\nif X:\n if X:\n        def bad(a, b):\n            ...\n"
_MULTIBYTE_LINE_SOURCE = "X = 'a{character}b'\n\u00e9 = X\nif \u00e9:\n    def bad(a, b):\n        ...\n"


@pytest.fixture
def schema() -> dict[str, object]:  # pyright: ignore[reportReturnType]
    """Load the JSON schema for validation."""
    schema_path = Path(__file__).parents[2] / "schemas" / "pyrigor-diagnostics-v2.json"
    assert schema_path.exists()
    return cast("dict[str, object]", json.loads(schema_path.read_text(encoding="utf-8")))


def _assert_valid_schema(*, document: dict[str, object], schema: dict[str, object]) -> None:
    """Assert that a JSON output document conforms to the published schema."""
    jsonschema.Draft202012Validator(schema).validate(document)  # pyright: ignore[reportUnknownMemberType]


def test_json_output_reports_clean_summary(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object]
) -> None:
    """JSON mode emits one complete document for a clean file."""
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("def apply_correction(*, weight, bias):\n    ...\n")

    assert not main(paths=[str(clean_file)], output_format="json")

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document, schema=schema)
    assert (
        set(document),
        document["schema_version"],
        document["tool"]["name"],
        bool(document["tool"]["version"]),
        document["findings"] == document["suppressed"] == document["errors"] == [],
        document["summary"],
        list(document["rules"]),
    ) == (
        {"schema_version", "tool", "findings", "suppressed", "rules", "errors", "summary"},
        _SCHEMA_VERSION,
        _TOOL_NAME,
        True,
        True,
        {"files_checked": 1},
        sorted(entry.rule.name for entry in CHECKERS),
    )
    for entry in CHECKERS:
        _assert_rule_metadata(
            metadata=document["rules"][entry.rule.name], rule=entry.rule, release=document["tool"]["version"]
        )


def _assert_rule_metadata(*, metadata: dict[str, object], rule: Rule, release: str) -> None:
    """Check a selected rule's identity, release-pinned documentation and optional applicability."""
    assert (metadata["symbolic_name"], metadata["fix_availability"], metadata["url"]) == (
        rule.symbolic_name,
        rule.fix_availability.value,
        f"https://github.com/jarl-hoyem/pyrigor/blob/v{release}/guidelines/{rule.name}-{rule.symbolic_name}.md",
    )
    assert (_APPLICABILITY in metadata) == (rule.applicability is not None)
    assert metadata.get(_APPLICABILITY) == (rule.applicability.value if rule.applicability is not None else None)


def test_json_output_includes_finding_metadata(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object]
) -> None:
    """JSON mode emits canonical spans, messages, symbols and empty finding fixes."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def apply_correction(weight, bias):\n    ...\n")

    assert main(paths=[str(bad_file)], output_format="json") == 1

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document, schema=schema)
    finding = document["findings"][0]
    header = "def apply_correction(weight, bias):"
    assert finding == {
        "code": "PYR402",
        "message": "Function 'apply_correction' " + Rule.PYR402.problem,
        "level": "warning",
        "spans": [
            {
                "file_name": Path(relpath(bad_file)).as_posix(),
                "byte_start": 0,
                "byte_end": len(header.encode()),
                "line_start": 1,
                "column_start": 1,
                "line_end": 1,
                "column_end": len(header) + 1,
                "is_primary": True,
            }
        ],
        "enclosing_symbol": {"kind": "function", "name": "apply_correction"},
        "fixes": [],
    }


def test_json_output_reports_no_fixes_for_a_rule_without_applicability(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object]
) -> None:
    """Rules without fixes omit applicability, and findings carry an empty fixes list."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("x: tuple[int, str] = (1, 'a')\n")

    assert main(paths=[str(bad_file)], output_format="json") == 1

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document, schema=schema)
    assert document["findings"][0]["fixes"] == []
    assert document["rules"]["PYR301"]["fix_availability"] == _NO_FIXES
    assert _APPLICABILITY not in document["rules"]["PYR301"]


def test_json_output_is_indented_rather_than_one_line(*, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The document is printed with two-space indentation, so a person can read it in a terminal.

    Every other test parses the output, which leaves the serialisation itself unchecked.
    """
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("def apply_correction(*, weight, bias):\n    ...\n")

    assert not main(paths=[str(clean_file)], output_format="json")

    raw = capsys.readouterr().out
    assert raw.startswith('{\n  "schema_version": 2,\n')
    assert raw.endswith("}\n")


def test_json_output_leaves_non_ascii_text_unescaped(*, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A non-ASCII name is written as itself, not as an escape sequence.

    The document is UTF-8, so escaping would only make it harder to read.
    """
    source_file = tmp_path / "source.py"
    source_file.write_text(f"def {_NON_ASCII_NAME}(weight, bias):\n    ...\n", encoding="utf-8")

    assert main(paths=[str(source_file)], output_format="json") == 1

    raw = capsys.readouterr().out
    assert f"'{_NON_ASCII_NAME}'" in raw
    assert _ESCAPED_NON_ASCII not in raw


def test_json_output_counts_suppressed_findings(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object]
) -> None:
    """JSON mode keeps suppressed findings in their own list."""
    suppressed_file = tmp_path / "suppressed.py"
    suppressed_file.write_text("def apply_correction(weight, bias):  # pyrigor 402 # external API\n    ...\n")

    assert not main(paths=[str(suppressed_file)], output_format="json")

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document, schema=schema)
    assert (
        document["findings"],
        len(document["suppressed"]),
        document["suppressed"][0]["code"],
        document["suppressed"][0]["fixes"],
        document["summary"],
    ) == (
        [],
        1,
        Rule.PYR402.name,
        [],
        {"files_checked": 1},
    )


def test_json_output_reports_parse_error_without_fake_finding(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object]
) -> None:
    """JSON mode reports syntax failures as errors and keeps stdout valid JSON."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def broken(:\n    pass\n")

    assert not main(paths=[str(bad_file)], output_format="json")

    captured = capsys.readouterr()
    document = json.loads(captured.out)
    error = document["errors"][0]
    _assert_valid_schema(document=document, schema=schema)
    assert (document["findings"], error["file_name"], error["kind"], str(bad_file) in captured.err) == (
        [],
        Path(relpath(bad_file)).as_posix(),
        "parse_error",
        True,
    )


def test_json_output_reports_read_error(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object]
) -> None:
    """JSON mode reports undecodable files as read errors."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_bytes(b"\xa4 not utf-8")

    assert not main(paths=[str(bad_file)], output_format="json")

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document, schema=schema)
    assert document["errors"][0]["kind"] == _READ_ERROR


def test_json_schema_rejects_non_rule_metadata_keys(*, schema: dict[str, object]) -> None:
    """The schema restricts rule metadata keys to PYR codes."""
    with pytest.raises(jsonschema.ValidationError):
        _assert_valid_schema(
            document={
                "schema_version": 2,
                "tool": {"name": "pyrigor", "version": "1.0.0"},
                "findings": [],
                "suppressed": [],
                "rules": {"not-a-rule": {}},
                "errors": [],
                "summary": {"files_checked": 0},
            },
            schema=schema,
        )


def test_json_location_converts_utf8_byte_columns_to_code_points(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object]
) -> None:
    """JSON locations use character columns for non-ASCII source spans."""
    source_file = tmp_path / "unicode.py"
    source_file.write_text("def café(a, b):\n    return a\n", encoding="utf-8")

    assert main(paths=[str(source_file)], output_format="json") == 1

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document, schema=schema)
    span = document["findings"][0]["spans"][0]
    assert span["line_end"] == 1
    assert span["column_end"] == len("def café(a, b):") + 1
    assert span["byte_end"] == len("def café(a, b):".encode())


def _expected_location(*, source_file: Path) -> dict[str, dict[str, int]]:
    """Compute the expected location of the first function, through the v2 position index.

    The index reads the file's raw bytes, so it is not dependent on the command line interface's own conversion.
    """
    raw = source_file.read_bytes()
    source = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    tree = ast.parse(source)
    function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
    function.end_lineno = function.lineno
    function.end_col_offset = len(source.split("\n")[function.lineno - 1].rstrip().encode())
    # noinspection PyTypeChecker
    # FunctionDef is a real subtype of stmt; mypy, pyright and ty all confirm this line type-check.
    span = make_span(node=function, index=PositionIndex(raw=raw), file_name=FileName("x.py"))
    return {
        "start": {"line": span.line_start, "column": span.column_start},
        "end": {"line": span.line_end, "column": span.column_end},
    }


@pytest.mark.parametrize("character", NON_PYTHON_LINE_BREAKS, ids=LINE_BREAK_IDS)
@pytest.mark.parametrize("template", [_SHIFTED_LINE_SOURCE, _MULTIBYTE_LINE_SOURCE], ids=["shifted", "multibyte"])
def test_json_location_survives_a_break_only_splitlines_recognises(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object], character: str, template: str
) -> None:
    """A character above the finding that only str.splitlines() breaks on leaves the location correct.

    Reading the wrong line crashes the run when the slice cuts a character in half and reports a wrong column
    otherwise.
    """
    source_file = tmp_path / "break.py"
    source_file.write_text(template.format(character=character), encoding="utf-8")

    assert main(paths=[str(source_file)], output_format="json") == 1

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document, schema=schema)
    span = document["findings"][0]["spans"][0]
    assert {
        "start": {"line": span["line_start"], "column": span["column_start"]},
        "end": {"line": span["line_end"], "column": span["column_end"]},
    } == _expected_location(source_file=source_file)


def test_json_output_reports_every_file_when_one_holds_a_non_python_line_break(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object]
) -> None:
    """One awkward file does not cost the findings of the others."""
    plain_file = tmp_path / "plain.py"
    plain_file.write_text("def plain(a, b):\n    ...\n", encoding="utf-8")
    break_file = tmp_path / "break.py"
    break_file.write_text(_MULTIBYTE_LINE_SOURCE.format(character=chr(0x2028)), encoding="utf-8")

    assert main(paths=[str(plain_file), str(break_file)], output_format="json") == 1

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document, schema=schema)
    assert {finding["spans"][0]["file_name"] for finding in document["findings"]} == {
        Path(relpath(path)).as_posix() for path in (plain_file, break_file)
    }


@pytest.mark.parametrize("select", [{"PYR402"}, {"unregistered-rule"}], ids=["one", "empty"])
def test_json_output_includes_exactly_selected_rules(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object], select: set[str]
) -> None:
    """Selected rules remain in metadata when no findings are produced."""
    source_file = tmp_path / "empty.py"
    source_file.write_bytes(b"")

    assert not main(paths=[str(source_file)], select=select, output_format="json")

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document, schema=schema)
    assert set(document["rules"]) == select.intersection({"PYR402"})
    assert document["findings"] == document["suppressed"] == document["errors"] == []
    assert document["summary"] == {"files_checked": 1}


@pytest.mark.parametrize("comment", ["# pyrigor 402", "# pyrigor 402 #", "# PyRigor 402 # reason"])
def test_json_output_reports_malformed_suppressions_separately(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object], comment: str
) -> None:
    """Malformed comments retain the finding and add a positioned operational error."""
    source_file = tmp_path / "malformed.py"
    source_file.write_text(f"def bad(a, b):  {comment}\n    ...\n", encoding="utf-8")

    assert main(paths=[str(source_file)], select={"PYR402"}, output_format="json") == 1

    captured = capsys.readouterr()
    document = json.loads(captured.out)
    _assert_valid_schema(document=document, schema=schema)
    assert (
        len(document["findings"]) == len(document["errors"]) == 1,
        document["suppressed"],
    ) == (
        True,
        [],
    )
    error = document["errors"][0]
    assert (
        error["kind"],
        error["line"],
        error["column"],
        error["file_name"],
        _WARNING_PREFIX in captured.err,
    ) == (
        _MALFORMED_SUPPRESSION,
        1,
        len("def bad(a, b):  ") + 1,
        Path(relpath(source_file)).as_posix(),
        True,
    )


def test_json_output_reads_raw_source_once(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every checker shares one raw-byte read, without a text-mode reread."""
    source_file = tmp_path / "source.py"
    source_file.write_bytes(b"def bad(a, b):\n    ...\n")
    original_read_bytes = Path.read_bytes
    original_read_text = Path.read_text
    reads: list[Path] = []

    def read_bytes(self: Path) -> bytes:
        """Record source reads while preserving the real file reader."""
        if self == source_file:
            reads.append(self)
        return original_read_bytes(self)

    def read_text(self: Path, *_args: object, **_kwargs: object) -> str:
        """Reject a second text-mode source read."""
        assert self != source_file
        return original_read_text(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    monkeypatch.setattr(Path, "read_text", read_text)

    assert main(paths=[str(source_file)], output_format="json") == 1
    assert reads == [source_file]
    assert len(json.loads(capsys.readouterr().out)["findings"]) == 1


@pytest.mark.parametrize("line_break", [b"\n", b"\r\n", b"\r"], ids=["lf", "crlf", "cr"])
@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"], ids=["plain", "bom"])
def test_json_output_retains_raw_offsets_and_normalised_positions(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object], line_break: bytes, bom: bytes
) -> None:
    """Raw offsets include BOM and line-break bytes while columns count code points."""
    source_file = tmp_path / "unicode.py"
    prefix = "label = 'é'".encode()
    header = "def café(a, b):"
    raw = bom + prefix + line_break + header.encode() + line_break + b"    ..." + line_break
    source_file.write_bytes(raw)

    assert main(paths=[str(source_file)], select={"PYR402"}, output_format="json") == 1

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document, schema=schema)
    span = document["findings"][0]["spans"][0]
    assert (
        span["byte_start"],
        raw[span["byte_start"] : span["byte_end"]].decode(),
        span["line_start"] == span["line_end"] == 2,
        span["column_start"],
        span["column_end"],
    ) == (
        len(bom + prefix + line_break),
        header,
        True,
        1,
        len(header) + 1,
    )


class _RuleCase(NamedTuple):
    """One registered rule's source, expected subject and enclosing scope."""

    rule: Rule
    source: str
    subject: str
    kind: str
    symbol: str


@pytest.mark.parametrize(
    "case",
    [
        _RuleCase(
            rule=Rule.PYR301,
            source="value: tuple[int, str] = (1, 'a')\n",
            subject="Variable 'value'",
            kind="module",
            symbol="<module>",
        ),
        _RuleCase(
            rule=Rule.PYR401,
            source="def pair() -> tuple[int, str]:\n    ...\n",
            subject="Function 'pair'",
            kind="function",
            symbol="pair",
        ),
        _RuleCase(
            rule=Rule.PYR402,
            source="def bad(a, b):\n    ...\n",
            subject="Function 'bad'",
            kind="function",
            symbol="bad",
        ),
        _RuleCase(
            rule=Rule.PYR403,
            source="def bad(a):\n    ...\n",
            subject="Function 'bad'",
            kind="function",
            symbol="bad",
        ),
        _RuleCase(
            rule=Rule.PYR405,
            source="def bad(*, a: tuple[int, str]):\n    ...\n",
            subject="Function 'bad'",
            kind="function",
            symbol="bad",
        ),
        _RuleCase(
            rule=Rule.PYR406,
            source="def value() -> int:\n    ...\nvalue()\n",
            subject="Call 'value'",
            kind="module",
            symbol="<module>",
        ),
    ],
    ids=["301", "401", "402", "403", "405", "406"],
)
def test_json_output_uses_canonical_messages_and_symbols_for_every_rule(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object], case: _RuleCase
) -> None:
    """All registered rules serialise their problem text and the enclosing scope."""
    source_file = tmp_path / "source.py"
    source_file.write_text(case.source, encoding="utf-8")

    assert main(paths=[str(source_file)], select={case.rule.name}, output_format="json") == 1

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document, schema=schema)
    assert len(document["findings"]) == 1
    finding = document["findings"][0]
    assert (
        finding["code"],
        finding["message"],
        finding["level"],
        finding["enclosing_symbol"],
        finding["fixes"],
    ) == (
        case.rule.name,
        f"{case.subject} {case.rule.problem}",
        case.rule.severity.name.lower(),
        {"kind": case.kind, "name": case.symbol},
        [],
    )


class _TokenisationCase(NamedTuple):
    """Expected shared source work for a checker selection and suppression partition."""

    source: str
    select: set[str]
    kept: int
    suppressed: int
    tokenisations: int


@pytest.mark.parametrize(
    "case",
    [
        _TokenisationCase(
            source="def first(a, b):  # pyrigor 402 # external API\n    ...\ndef second(a, b):\n    ...\n",
            select={"PYR402"},
            kept=1,
            suppressed=1,
            tokenisations=1,
        ),
        _TokenisationCase(
            source="first: tuple[int, str] = (1, 'a')  # pyrigor 301 # external API\n\n"
            "second: tuple[int, str] = (2, 'b')\n",
            select={"PYR301"},
            kept=1,
            suppressed=1,
            tokenisations=1,
        ),
        _TokenisationCase(
            source="def value() -> int:\n    ...\nvalue()  # pyrigor 406 # deliberate discard\n\nvalue()\n",
            select={"PYR406"},
            kept=1,
            suppressed=1,
            tokenisations=1,
        ),
        _TokenisationCase(
            source="def clean(*, a, b):  # pyrigor 402 # external API\n    ...\n",
            select={"PYR402"},
            kept=0,
            suppressed=0,
            tokenisations=0,
        ),
    ],
    ids=["function-headers", "assignments", "calls", "clean"],
)
def test_json_output_shares_one_token_stream_for_findings_and_suppression(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object], case: _TokenisationCase
) -> None:
    """Header spans and suppression share one token stream, and clean files need no token stream."""
    source_file = tmp_path / "source.py"
    source_file.write_text(case.source, encoding="utf-8")

    with patch.object(tokenize, "generate_tokens", wraps=tokenize.generate_tokens) as generate_tokens:
        assert (
            main(paths=[str(source_file)], select=case.select, output_format="json"),
            generate_tokens.call_count,
        ) == (
            int(bool(case.kept)),
            case.tokenisations,
        )

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document, schema=schema)
    assert (
        len(document["findings"]),
        len(document["suppressed"]),
        document["errors"],
    ) == (
        case.kept,
        case.suppressed,
        [],
    )


def test_json_output_normalises_qualified_symbol_and_retains_raw_span(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], schema: dict[str, object]
) -> None:
    """Messages and symbols use Python's identifier normalisation while spans retain source spelling."""
    source_file = tmp_path / "source.py"
    source_file.write_text("class Outer:\n    def \u212a(self, a, b):\n        ...\n", encoding="utf-8")

    assert main(paths=[str(source_file)], select={"PYR402"}, output_format="json") == 1

    document = json.loads(capsys.readouterr().out)
    _assert_valid_schema(document=document, schema=schema)
    finding = document["findings"][0]
    assert finding["message"] == f"Function 'K' {Rule.PYR402.problem}"
    assert finding["enclosing_symbol"] == {"kind": "method", "name": "Outer.K"}
    span = finding["spans"][0]
    assert source_file.read_bytes()[span["byte_start"] : span["byte_end"]].decode() == _NORMALISED_HEADER_SOURCE


@pytest.mark.parametrize("encoding", ["ascii", "cp1252"])
def test_json_entry_point_writes_utf8_to_a_pipe_with_a_legacy_encoding(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, schema: dict[str, object], encoding: str
) -> None:
    """A real text stream emits UTF-8 JSON even when the process inherited an ASCII or Windows encoding."""
    name = "\u00e9\U00010400"
    source_file = tmp_path / "unicode.py"
    source_file.write_text(f"def {name}(a, b):\n    ...\n", encoding="utf-8")
    buffer = BytesIO()

    with TextIOWrapper(buffer, encoding=encoding, newline="\n") as stdout, monkeypatch.context() as patched:
        patched.setattr(sys, "stdout", stdout)
        patched.setattr(sys, "argv", ["pyrigor", "--output-format=json", "--select=PYR402", str(source_file)])
        with pytest.raises(SystemExit) as caught:
            run()
        assert caught.value.code == 1
        stdout.flush()
        raw = buffer.getvalue()

    output = raw.decode()
    document = json.loads(output)
    _assert_valid_schema(document=document, schema=schema)
    assert (
        name in output,
        _ESCAPED_NON_ASCII_PREFIX not in output,
        _ESCAPED_ASTRAL_PREFIX not in output,
        document["findings"][0]["enclosing_symbol"],
        document["findings"][0]["message"],
    ) == (
        True,
        True,
        True,
        {"kind": "function", "name": name},
        f"Function '{name}' {Rule.PYR402.problem}",
    )


def test_json_entry_point_supports_a_stringio_stdout(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, schema: dict[str, object]
) -> None:
    """In-memory text capture works without a stream reconfigure method."""
    source_file = tmp_path / "source.py"
    source_file.write_bytes(b"def bad(a, b):\n    ...\n")
    stdout = StringIO()

    with monkeypatch.context() as patched:
        patched.setattr(sys, "stdout", stdout)
        patched.setattr(sys, "argv", ["pyrigor", "--output-format=json", "--select=PYR402", str(source_file)])
        with pytest.raises(SystemExit) as caught:
            run()
        assert caught.value.code == 1

    document = json.loads(stdout.getvalue())
    _assert_valid_schema(document=document, schema=schema)
    assert len(document["findings"]) == 1
