# Ruff owns this file's formatting; PyCharm disagrees on continuation indentation and slice-colon spacing.
# noinspection PyPep8,IncorrectFormatting
"""Cross-check challenging signature spans, suppression and edits against original bytes."""

import json
import sys
from itertools import product
from pathlib import Path
from typing import NamedTuple

import jsonschema
import pytest
from jsonschema.protocols import Validator

from pyrigor.checkers.cli import main, run
from pyrigor.rules import Rule
from tests.diagnostics_v2_support import Json, load_v2_schema


class _Layout(NamedTuple):
    """Original byte layout and the explicit fixer operation."""

    newline: bytes
    bom: bytes
    option: str
    location: str


class _Name(NamedTuple):
    """Source spelling and independently specified Python identifier spelling."""

    source: str
    canonical: str


def _document_validator() -> Validator:
    """Expose the schema validator through its published typed interface."""
    return jsonschema.Draft202012Validator(load_v2_schema())


class _Source(NamedTuple):
    """Independent byte expectations for the signature and its single insertion."""

    original: bytes
    prefix: bytes
    signature: bytes
    fixed: bytes


def _source(*, name: _Name, layout: _Layout) -> _Source:
    """Build the source and oracle directly from known byte fragments."""
    comment = "# pyrigor 402 # deliberate test"
    signature_comment = {"signature": comment, "body": "", "nested-decorator": ""}[layout.location]
    body_comment = {"signature": "", "body": comment, "nested-decorator": ""}[layout.location]
    decorator_comment = {"signature": "", "body": "", "nested-decorator": comment}[layout.location]
    prefix = "label = '\u00e9\u2028\U0001f600'\n@decorate(lambda: {'outer': 1})\n"
    signature = (
        f"async def {name.source}(\n"
        f"    first: dict[str, int] = {{'\u00e9': 1}}, {signature_comment}\n"
        "    second=lambda: {'value': 2},\n"
        ") -> (lambda: {'annotation': 3}):"
    )
    body = (
        f"\n    {body_comment}\n"
        "    @decorate(\n"
        f"        lambda: {{'nested': 4}} {decorator_comment}\n"
        "    )\n"
        "    async def inner():\n"
        "        pass\n"
    )
    raw_prefix = layout.bom + prefix.encode().replace(b"\n", layout.newline)
    raw_signature = signature.encode().replace(b"\n", layout.newline)
    original = raw_prefix + raw_signature + body.encode().replace(b"\n", layout.newline)
    insertion = f"async def {name.source}(".encode()
    return _Source(original, raw_prefix, raw_signature, original.replace(insertion, insertion + b"*, "))


@pytest.mark.parametrize("name", [_Name("\uff2b", "K"), _Name("\ufb03", "ffi"), _Name("\U00010000", "\U00010000")])
@pytest.mark.parametrize(
    "layout",
    [
        _Layout(*values)
        for values in product(
            [b"\n", b"\r\n", b"\r"],
            [b"", b"\xef\xbb\xbf"],
            ["--fix", "--diff"],
            ["signature", "body", "nested-decorator"],
        )
    ],
)
def test_complex_signature_suppression_and_fixes_preserve_original_bytes(
    *,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    name: _Name,
    layout: _Layout,
) -> None:
    """Colons in decorators, defaults and annotations cannot move the span into the body."""
    source = _source(name=name, layout=layout)
    source_file = tmp_path / "source.py"
    source_file.write_bytes(source.original)
    main(paths=[str(source_file)], select={Rule.PYR402.name}, output_format="json")
    document: Json = json.loads(capsys.readouterr().out)
    _document_validator().validate(document)
    collection = {"signature": "suppressed", "body": "findings", "nested-decorator": "findings"}[layout.location]
    finding = document[collection][0]
    span = finding["spans"][0]
    assert (
        span["byte_start"],
        span["byte_end"],
        span["line_start"],
        span["column_start"],
        source.original[span["byte_start"] : span["byte_end"]],
        finding["enclosing_symbol"]["name"],
    ) == (len(source.prefix), len(source.prefix + source.signature), 3, 1, source.signature, name.canonical)
    monkeypatch.setattr(sys, "argv", ["pyrigor", layout.option, "--select=PYR402", str(source_file)])
    with pytest.raises(SystemExit) as caught:
        run()
    captured = capsys.readouterr()
    expected = {
        ("--fix", "signature"): source.original,
        ("--diff", "signature"): source.original,
        ("--fix", "body"): source.fixed,
        ("--diff", "body"): source.original,
        ("--fix", "nested-decorator"): source.fixed,
        ("--diff", "nested-decorator"): source.original,
    }[layout.option, layout.location]
    assert (caught.value.code, captured.err, source_file.read_bytes()) == (0, "", expected)


class _BlankLineCase(NamedTuple):
    """Original leading bytes and independently specified diff context."""

    prefix: bytes
    newline: bytes
    diff_context: str
    lines: int


@pytest.mark.parametrize("option", ["--fix", "--diff"])
@pytest.mark.parametrize(
    "case",
    [
        _BlankLineCase(b"\r\r", b"\r", " \r \r", 4),
        _BlankLineCase(b"# comment\r\r", b"\r", " # comment\r \r", 4),
        _BlankLineCase(b"\r", b"\r", " \r", 3),
        _BlankLineCase(b"\r\n\r\n", b"\r\n", " \r\n \r\n", 4),
    ],
    ids=["cr-blank", "cr-comment-blank", "single-cr-control", "crlf-blank-control"],
)
def test_cr_only_blank_lines_do_not_crash_fix_or_diff(
    *,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    option: str,
    case: _BlankLineCase,
) -> None:
    """The #348 reproductions and negative controls preserve all original line-ending bytes."""
    original = case.prefix + b"def f(a, b):" + case.newline + b"    pass" + case.newline
    fixed = original.replace(b"def f(a, b):", b"def f(*, a, b):")
    source_file = tmp_path / "cr_only.py"
    source_file.write_bytes(original)
    monkeypatch.setattr(sys, "argv", ["pyrigor", option, "--select=PYR402", str(source_file)])
    with pytest.raises(SystemExit) as caught:
        run()
    captured = capsys.readouterr()
    expected_source = {"--fix": fixed, "--diff": original}[option]
    expected_output = {
        "--fix": f"Fixed {source_file}\n",
        "--diff": (
            f"--- {source_file}\n+++ {source_file}\n@@ -1,{case.lines} +1,{case.lines} @@\n"
            + case.diff_context
            + "-def f(a, b):"
            + case.newline.decode()
            + "+def f(*, a, b):"
            + case.newline.decode()
            + "     pass"
            + case.newline.decode()
        ),
    }[option]
    assert (caught.value.code, captured.err, captured.out, source_file.read_bytes()) == (
        0,
        "",
        expected_output,
        expected_source,
    )
