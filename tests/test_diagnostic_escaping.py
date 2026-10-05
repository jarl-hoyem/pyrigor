"""Verify visible diagnostic text without weakening file-name or symbol identity rules."""

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import NamedTuple
from unittest.mock import patch

import pytest

from pyrigor import findings
from pyrigor.checkers.cli import run
from pyrigor.diagnostics import CheckError, error_to_json
from pyrigor.findings import EnclosingSymbol, FileName, SymbolKind, finding_to_json
from pyrigor.fixers.pyr402_keyword_only_arguments_fixer import FixRejectedError
from pyrigor.rules import Rule
from tests.checker_helpers import finding_at
from tests.diagnostics_v2_support import definition_validator

_JSON_OUTPUT_FORMAT = "json"
_WRITE_FAILURE = "write"

_CONTROL_CASES = [
    (chr(code_point), {9: r"\t", 10: r"\n", 13: r"\r"}.get(code_point, f"\\x{code_point:02x}"))
    for code_point in (*range(32), *range(0x7F, 0xA0))
]
_UNICODE_CASES = [
    (chr(code_point), f"\\u{code_point:04x}")
    for code_point in (
        0x034F,
        0x061C,
        0x115F,
        0x1160,
        0x180E,
        *range(0x200B, 0x2010),
        *range(0x202A, 0x202F),
        *range(0x2060, 0x2070),
        0x3164,
        0xFEFF,
        0xFFA0,
        *range(0xFFF9, 0xFFFC),
    )
]
_ESCAPE_CASES = [*_CONTROL_CASES, ("\u00ad", r"\xad"), *_UNICODE_CASES]
_ORDINARY_TEXT = [
    "",
    "ordinary text",
    "café",
    "'quoted' \"text\"",
    r"\u034f",
    r"C:\new\test",
    "\u00a0",
    "\U00010000",
]


@pytest.mark.parametrize(("character", "visible"), _ESCAPE_CASES)
def test_finding_and_error_serialisation_use_the_same_visible_spelling(*, character: str, visible: str) -> None:
    """Every forbidden character has an explicit spelling in both diagnostic payloads."""
    message = f"before{character}after"
    expected = f"before{visible}after"
    original = replace(finding_at(line=1, end_line=1, column=1, rule=Rule.PYR402), message=message)
    payload = finding_to_json(finding=original)
    error = CheckError(file_name=FileName("test.py"), kind="read_error", message=message)
    assert payload["message"] == expected
    assert error_to_json(error=error)["message"] == expected
    assert original.message == error.message == message
    definition_validator(definition="Finding").validate(json.loads(json.dumps(payload)))


@pytest.mark.parametrize("text", _ORDINARY_TEXT)
def test_ordinary_text_and_literal_backslashes_remain_unchanged(*, text: str) -> None:
    """An output boundary must not reinterpret a literal escape or change permitted Unicode."""
    assert findings.escape_diagnostic_text(text=text) == text


@pytest.mark.parametrize(("character", "visible"), _ESCAPE_CASES)
def test_visible_output_is_not_double_escaped(*, character: str, visible: str) -> None:
    """Passing the shared display text through another output boundary is harmless."""
    text = f"{character}{visible}\\"
    expected = f"{visible}{visible}\\"
    once = findings.escape_diagnostic_text(text=text)
    assert once == expected
    assert findings.escape_diagnostic_text(text=once) == once


@pytest.mark.parametrize(
    ("character", "visible"),
    [("\u00a0", r"\xa0"), ("\u2028", r"\u2028"), ("\U000e0001", r"\U000e0001")],
)
def test_source_expressions_keep_their_existing_nonprintable_spelling(*, character: str, visible: str) -> None:
    """The source-subject mode preserves established display behaviour without broadening the default policy."""
    assert findings.escape_diagnostic_text(text=character) == character
    assert findings.escape_diagnostic_text(text=character, escape_nonprintable=True) == visible


@pytest.mark.parametrize("code_point", [0x034F, 0x115F, 0x1160, 0x200C, 0x200D])
@pytest.mark.parametrize("template", ["a{character}", "outer.<locals>.a{character}b\u034f"])
def test_serialised_symbol_identity_decodes_to_the_unchanged_internal_name(*, code_point: int, template: str) -> None:
    """Individual and mixed qualified names stay distinct and reversible after serialisation."""
    character = chr(code_point)
    if not ("a" + character).isidentifier():
        pytest.skip("This Python version does not accept the identifier character")
    name = template.format(character=character)
    symbol = EnclosingSymbol(kind=SymbolKind.FUNCTION, name=name)
    original = replace(finding_at(line=1, end_line=1, column=1, rule=Rule.PYR402), enclosing_symbol=symbol)
    payload = json.loads(json.dumps(finding_to_json(finding=original)))
    escaped = payload["enclosing_symbol"]["name"]
    other = replace(original, enclosing_symbol=EnclosingSymbol(kind=SymbolKind.FUNCTION, name=name + "b"))
    other_payload = json.loads(json.dumps(finding_to_json(finding=other)))
    definition_validator(definition="Finding").validate(payload)
    assert (
        character in escaped,
        escaped.encode("ascii").decode("unicode_escape"),
        original.enclosing_symbol is symbol,
        symbol.name,
        finding_to_json(finding=original),
        escaped == other_payload["enclosing_symbol"]["name"],
    ) == (False, name, True, name, payload, False)


def test_suppressed_findings_are_escaped_without_changing_the_suppression(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """JSON still carries suppressed findings, with their internal identities rendered visibly."""
    path = tmp_path / "suppressed.py"
    path.write_text("# pyrigor 402 # public API\ndef a\u034f(left, right): pass\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["pyrigor", "--output-format=json", "--select=PYR402", str(path)])
    with pytest.raises(SystemExit) as caught:
        run()
    captured = capsys.readouterr()
    document = json.loads(captured.out)
    definition_validator(definition="Document").validate(document)
    character = "\u034f"
    assert (
        caught.value.code,
        captured.err,
        document["findings"],
        len(document["suppressed"]),
        document["suppressed"][0]["enclosing_symbol"]["name"],
        character in captured.out,
    ) == (0, "", [], 1, r"a\u034f", False)


@pytest.mark.parametrize("character", ["\u200c", "\u200d"])
def test_an_identifier_rejected_by_python_remains_a_parse_error(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, character: str
) -> None:
    """Display escaping does not change which Python source can be parsed."""
    if ("a" + character).isidentifier():
        pytest.skip("This Python version accepts the identifier character")
    path = tmp_path / "syntax.py"
    path.write_text(f"def a{character}(left, right): pass\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["pyrigor", "--output-format=json", str(path)])
    with pytest.raises(SystemExit) as caught:
        run()
    captured = capsys.readouterr()
    document = json.loads(captured.out)
    definition_validator(definition="Document").validate(document)
    assert (
        caught.value.code,
        document["findings"],
        [error["kind"] for error in document["errors"]],
        character in captured.out + captured.err,
    ) == (0, [], ["parse_error"], False)


class _FixReadCase(NamedTuple):
    """A fixer mode and its raw and visible read-error character."""

    option: str
    character: str
    visible: str


@pytest.mark.parametrize(
    "case",
    [
        _FixReadCase(option, character, visible)
        for option in ("--fix", "--diff")
        for character, visible in (("\u034f", r"\u034f"), ("\x1b", r"\x1b"), ("\u00ad", r"\xad"))
    ],
)
def test_fix_modes_render_operational_read_errors_with_the_shared_spelling(
    *,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    case: _FixReadCase,
) -> None:
    """A read-error message does not bypass the shared human-output boundary in fixer modes."""
    option, character, visible = case
    path = tmp_path / "unreadable.py"
    path.write_text("def apply(left, right): pass\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["pyrigor", option, "--select=PYR402", str(path)])
    with (
        patch.object(Path, "read_bytes", side_effect=OSError(f"problem {character}")),
        pytest.raises(SystemExit) as caught,
    ):
        run()
    captured = capsys.readouterr()
    assert (caught.value.code, captured.out, character in captured.err, visible in captured.err) == (0, "", False, True)


@pytest.mark.parametrize("output_format", ["human", "json"])
def test_mixed_affected_and_clean_finding_files_are_both_reported(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, output_format: str
) -> None:
    """An affected finding must not hide other findings from a directory run."""
    (tmp_path / "affected.py").write_text("def a\u034f(left, right): pass\n", encoding="utf-8")
    (tmp_path / "clean.py").write_text("def plain(left, right): pass\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["pyrigor", f"--output-format={output_format}", "--select=PYR402", str(tmp_path)])
    with pytest.raises(SystemExit) as caught:
        run()
    captured = capsys.readouterr()
    character = "\u034f"
    visible_name = r"a\u034f"
    ordinary_name = "plain"
    assert (caught.value.code, captured.err, character in captured.out) == (1, "", False)
    if output_format == _JSON_OUTPUT_FORMAT:
        document = json.loads(captured.out)
        definition_validator(definition="Document").validate(document)
        assert (
            document["summary"]["files_checked"],
            document["findings"][0]["enclosing_symbol"]["name"],
            document["findings"][1]["enclosing_symbol"]["name"],
        ) == (2, visible_name, ordinary_name)
    else:
        assert (visible_name in captured.out, ordinary_name in captured.out) == (True, True)


@pytest.mark.parametrize("failure", ["write", "rejected"])
def test_fix_failure_messages_use_visible_text_without_changing_the_file(
    *,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    """Both write failures and rejected fixes use the same display spelling as other operational errors."""
    path = tmp_path / "fix.py"
    source = b"def apply(left, right): pass\n"
    path.write_bytes(source)
    monkeypatch.setattr(sys, "argv", ["pyrigor", "--fix", "--select=PYR402", str(path)])
    message = "problem \u034f"
    if failure == _WRITE_FAILURE:
        failed_operation = patch.object(Path, "write_bytes", side_effect=OSError(message))
        expected_exit = 1
    else:
        failed_operation = patch("pyrigor.checkers.cli.fix_source", side_effect=FixRejectedError(message))
        expected_exit = 0
    with failed_operation, pytest.raises(SystemExit) as caught:
        run()
    captured = capsys.readouterr()
    assert (caught.value.code, captured.out, path.read_bytes()) == (expected_exit, "", source)
    character = "\u034f"
    visible = r"\u034f"
    assert (character in captured.err, visible in captured.err) == (False, True)
