"""Make temporary producer limits explicit instead of emitting invalid v2 documents."""

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import NamedTuple
from unittest.mock import patch

import pytest

from pyrigor.checkers.cli import run
from pyrigor.diagnostics import require_supported_findings
from pyrigor.rules import Rule
from tests.checker_helpers import finding_at
from tests.diagnostics_v2_support import (
    HIDDEN_TEXT_REFERENCE,
    definition_validator,
    forbidden_hidden_characters,
    load_v2_schema,
)

_USAGE_ERROR = 2
_RELATIVE_FRAGMENT = "relative"
_CRASH_MESSAGE = "pyrigor crashed unexpectedly"
_GRAPHEME_JOINER_CODE_POINT = "U+034F"
_REJECTED_CODE_POINTS = [0x034F, 0x115F, 0x1160, 0x200C, 0x200D]


class _RejectedCase(NamedTuple):
    """One affected identifier and the field that will carry it."""

    code_point: int
    rule: Rule
    template: str


class _ErrorTextCase(NamedTuple):
    """An input character and the error context that may quote it."""

    character: str
    template: str


# noinspection IncorrectFormatting
@pytest.mark.parametrize("output_format", ["human", "json"])
@pytest.mark.parametrize(
    "case",
    [
        _RejectedCase(code_point, rule, template)
        for code_point in _REJECTED_CODE_POINTS
        for rule, template in (
            (Rule.PYR402, "def {name}(a, b):\n    pass\n"),
            (Rule.PYR301, "def {name}():\n    value: tuple[int, str] = (1, 'a')\n"),
        )
    ],
    ids=lambda case: f"U+{case.code_point:04X}-{case.rule.name}",
)
def test_rejected_identifiers_fail_without_emitting_a_document(
    *,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    case: _RejectedCase,
    output_format: str,
) -> None:
    """Detect each affected character whether it occurs in the subject or only the enclosing name."""
    name = "flagged" + chr(case.code_point)
    if not name.isidentifier():
        pytest.skip("This Python version rejects the character during parsing")
    source_file = tmp_path / "unsupported.py"
    source_file.write_text(case.template.format(name=name), encoding="utf-8")
    monkeypatch.setattr(
        sys, "argv", ["pyrigor", f"--output-format={output_format}", f"--select={case.rule.name}", str(source_file)]
    )
    with pytest.raises(SystemExit) as caught:
        run()
    captured = capsys.readouterr()
    assert (caught.value.code, captured.out, f"U+{case.code_point:04X}" in captured.err) == (_USAGE_ERROR, "", True)
    assert str(source_file) in captured.err.replace("\\\\", "\\")


@pytest.mark.parametrize("output_format", ["human", "json"])
def test_a_path_with_no_relative_form_is_a_clear_usage_error(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, output_format: str
) -> None:
    """A relative-path failure aborts before reading the source or printing a partial document."""
    source_file = tmp_path / "foreign.py"
    source_file.write_text("def flagged(a, b):\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["pyrigor", f"--output-format={output_format}", str(source_file)])
    with (
        patch("pyrigor.checkers.cli.os.path.relpath", side_effect=ValueError("different drive")),
        patch.object(Path, "read_bytes", side_effect=AssertionError("source must not be read")),
        pytest.raises(SystemExit) as caught,
    ):
        run()
    captured = capsys.readouterr()
    assert (caught.value.code, captured.out, _RELATIVE_FRAGMENT in captured.err) == (_USAGE_ERROR, "", True)
    assert str(source_file) in captured.err.replace("\\\\", "\\")


def test_plain_findings_without_optional_symbols_remain_supported() -> None:
    """The temporary guard preserves the canonical model's optional enclosing symbol."""
    require_supported_findings(findings=[finding_at(line=1, end_line=1, column=1, rule=Rule.PYR402)], path="test.py")


@pytest.mark.parametrize("output_format", ["human", "json"])
@pytest.mark.parametrize("character", ["\u3164", "\uffa0"])
def test_invisible_fillers_in_subscript_subjects_fail_explicitly(
    *,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    character: str,
    output_format: str,
) -> None:
    """Printable filler characters in literal subjects cannot bypass the interim text guard."""
    path = tmp_path / "subject.py"
    path.write_text(f"data['{character}']: tuple[int, str]\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["pyrigor", f"--output-format={output_format}", str(path)])
    with pytest.raises(SystemExit) as caught:
        run()
    captured = capsys.readouterr()
    assert caught.value.code == _USAGE_ERROR
    assert not captured.out
    assert f"U+{ord(character):04X}" in captured.err


# noinspection IncorrectFormatting
@pytest.mark.parametrize(
    "case",
    [
        _ErrorTextCase(character, template)
        for character in ("\u034f", "\u202e", "\u200b", "\x01")
        for template in ("def bad(a, b): # PYRIGOR 402 {character}\n    pass\n",)
    ]
    + [_ErrorTextCase("\u034f", "{character} = 1\n")],
)
@pytest.mark.parametrize("output_format", ["human", "json"])
def test_rejected_error_text_never_emits_invalid_or_partial_output(
    *,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    case: _ErrorTextCase,
    output_format: str,
) -> None:
    """An operational warning is subject to the same interim text limit as a rule finding."""
    character, template = case
    good = tmp_path / "a_good.py"
    good.write_text("def flagged(a, b): pass\n", encoding="utf-8")
    bad = tmp_path / "z_bad.py"
    bad.write_text(template.format(character=character), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["pyrigor", f"--output-format={output_format}", str(good), str(bad)])
    with pytest.raises(SystemExit) as caught:
        run()
    captured = capsys.readouterr()
    assert (
        caught.value.code,
        captured.out,
        _CRASH_MESSAGE in captured.err,
        f"U+{ord(character):04X}" in captured.err,
        str(bad) in captured.err.replace("\\\\", "\\"),
    ) == (_USAGE_ERROR, "", False, True, True)


@pytest.mark.parametrize("character", ["\u202e", "\u200b", "\x01"])
def test_already_escaped_parser_errors_remain_valid_diagnostics(
    *,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    character: str,
) -> None:
    """Python's visible parser escapes remain reportable rather than triggering the literal-text guard."""
    path = tmp_path / "syntax.py"
    path.write_text(character + " = 1\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["pyrigor", "--output-format=json", str(path)])
    with pytest.raises(SystemExit) as caught:
        run()
    captured = capsys.readouterr()
    definition_validator(definition="Document").validate(json.loads(captured.out))
    assert (caught.value.code, character in captured.out + captured.err) == (0, False)


def test_interim_guard_matches_the_schemas_rejected_text_characters() -> None:
    """Every forbidden literal text character is rejected, including printable fillers."""
    message_rules = load_v2_schema()["$defs"]["Finding"]["properties"]["message"]["allOf"]
    assert HIDDEN_TEXT_REFERENCE in message_rules
    base = finding_at(line=1, end_line=1, column=1, rule=Rule.PYR402)
    for character in forbidden_hidden_characters():
        with pytest.raises(ValueError, match=rf"U\+{ord(character):04X}"):
            require_supported_findings(findings=[replace(base, message="Subject " + character)], path="test.py")


# noinspection IncorrectFormatting
@pytest.mark.parametrize("output_format", ["human", "json"])
@pytest.mark.parametrize("source", [None, "def flagged(a, b): pass\n", "def broken(: pass\n"])
def test_rejected_file_names_cannot_enter_findings_or_errors(
    *,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    output_format: str,
    source: str | None,
) -> None:
    """The same file-name text limit applies to kept findings, read errors and parse errors."""
    path = tmp_path / "bad\u034f.py"
    if source is not None:
        path.write_text(source, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["pyrigor", f"--output-format={output_format}", str(path)])
    with pytest.raises(SystemExit) as caught:
        run()
    captured = capsys.readouterr()
    assert (
        caught.value.code,
        captured.out,
        _GRAPHEME_JOINER_CODE_POINT in captured.err,
        str(path) in captured.err.replace("\\\\", "\\"),
        _CRASH_MESSAGE in captured.err,
    ) == (_USAGE_ERROR, "", True, True, False)


# noinspection IncorrectFormatting
@pytest.mark.parametrize("output_format", ["human", "json"])
@pytest.mark.parametrize("directory_argument", [False, True])
def test_mixed_relative_and_unrepresentable_paths_fail_before_reading_any_file(
    *,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    output_format: str,
    directory_argument: bool,
) -> None:
    """Neither another good file nor directory expansion can turn a path failure into partial output."""
    good = tmp_path / "a_good.py"
    bad = tmp_path / "z_foreign.py"
    for path in (good, bad):
        path.write_text("def flagged(a, b): pass\n", encoding="utf-8")
    paths = [str(tmp_path)] if directory_argument else [str(good), str(bad)]
    monkeypatch.setattr(sys, "argv", ["pyrigor", f"--output-format={output_format}", *paths])

    def relative_path(*arguments: str) -> str:
        """Accept the positional argument list that os.path.relpath passes to its mock."""
        if arguments[0] == str(bad):
            raise ValueError("different drive")
        return good.name

    with (
        patch("pyrigor.checkers.cli.os.path.relpath", side_effect=relative_path),
        patch.object(Path, "read_bytes", side_effect=AssertionError("source must not be read")),
        pytest.raises(SystemExit) as caught,
    ):
        run()
    captured = capsys.readouterr()
    assert (
        caught.value.code,
        captured.out,
        str(bad) in captured.err.replace("\\\\", "\\"),
        _CRASH_MESSAGE in captured.err,
    ) == (_USAGE_ERROR, "", True, False)
