"""Exercise real primary spans and suppression boundaries under every Python newline spelling."""

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

_FUNCTION = "def flagged(a, b):\n    pass\n"
_CALL_PREFIX = "def compute() -> int:\n    return 1\n"
_FUNCTION_NAME = ("flagged",)
_MODULE_NAME = ("<module>",)


class _Case(NamedTuple):
    """A rule, original source and expected suppression membership."""

    rule: Rule
    source: str
    kept: tuple[str, ...]
    suppressed: tuple[str, ...]
    errors: int = 0


@pytest.mark.parametrize("line_break", ["\n", "\r\n", "\r"], ids=["lf", "crlf", "cr"])
@pytest.mark.parametrize(
    "case",
    [
        pytest.param(_Case(Rule.PYR402, _FUNCTION, _FUNCTION_NAME, ()), id="first-line"),
        pytest.param(
            _Case(Rule.PYR402, "def flagged(a, b):  # pyrigor 402 # API\n    pass\n", (), _FUNCTION_NAME),
            id="same-line",
        ),
        pytest.param(_Case(Rule.PYR402, "# pyrigor 402 # API\n" + _FUNCTION, (), _FUNCTION_NAME), id="line-above"),
        pytest.param(
            _Case(Rule.PYR402, "# pyrigor 402 # API\n\n" + _FUNCTION, _FUNCTION_NAME, ()), id="two-lines-above"
        ),
        pytest.param(
            _Case(Rule.PYR402, "def flagged(\n    a,  # pyrigor 402 # API\n    b,\n):\n    pass\n", (), _FUNCTION_NAME),
            id="signature-middle",
        ),
        pytest.param(
            _Case(Rule.PYR402, "def flagged(\n    a,\n    b,\n):  # pyrigor 402 # API\n    pass\n", (), _FUNCTION_NAME),
            id="signature-closing",
        ),
        pytest.param(
            _Case(Rule.PYR402, "def flagged(a, b):\n    # pyrigor 402 # body\n    pass\n", _FUNCTION_NAME, ()),
            id="own-body-line",
        ),
        pytest.param(
            _Case(Rule.PYR402, "def flagged(a, b):\n    pass  # pyrigor 402 # body\n", _FUNCTION_NAME, ()),
            id="trailing-body-line",
        ),
        pytest.param(
            _Case(
                Rule.PYR402,
                "def outer(a, b):\n    def inner(a, b):  # pyrigor 402 # API\n        pass\n",
                ("outer",),
                ("outer.<locals>.inner",),
            ),
            id="nested-comment",
        ),
        pytest.param(_Case(Rule.PYR402, _FUNCTION + "# pyrigor 402 # later\n", _FUNCTION_NAME, ()), id="after-span"),
        pytest.param(
            _Case(Rule.PYR402, "def flagged(a, b):  # pyrigor 402\n    pass\n", _FUNCTION_NAME, (), 1),
            id="missing-reason",
        ),
        pytest.param(
            _Case(
                Rule.PYR402, "# pyrigor 402 # API\ndef flagged(a, b):  # pyrigor 402\n    pass\n", (), _FUNCTION_NAME, 1
            ),
            id="valid-cannot-hide-malformed",
        ),
        pytest.param(
            _Case(Rule.PYR402, "@decorate  # pyrigor 402 # API\n@other\n" + _FUNCTION, _FUNCTION_NAME, ()),
            id="decorator-outside-span",
        ),
        pytest.param(
            _Case(Rule.PYR406, _CALL_PREFIX + "compute()  # pyrigor 406 # deliberate\n", (), _MODULE_NAME),
            id="call-same-line",
        ),
        pytest.param(
            _Case(Rule.PYR406, _CALL_PREFIX + "# pyrigor 406 # deliberate\ncompute()\n", (), _MODULE_NAME),
            id="call-line-above",
        ),
        pytest.param(
            _Case(Rule.PYR406, _CALL_PREFIX + "# pyrigor 406 # deliberate\n\ncompute()\n", _MODULE_NAME, ()),
            id="call-two-lines-above",
        ),
        pytest.param(
            _Case(Rule.PYR406, _CALL_PREFIX + "compute(\n    # pyrigor 406 # deliberate\n)\n", (), _MODULE_NAME),
            id="call-middle",
        ),
        pytest.param(
            _Case(Rule.PYR406, _CALL_PREFIX + "compute(\n)  # pyrigor 406 # deliberate\n", (), _MODULE_NAME),
            id="call-closing",
        ),
        pytest.param(
            _Case(Rule.PYR406, _CALL_PREFIX + "compute(\n)\n# pyrigor 406 # later\n", _MODULE_NAME, ()),
            id="call-after-span",
        ),
        pytest.param(
            _Case(Rule.PYR406, _CALL_PREFIX + "compute()  # pyrigor 406\n", _MODULE_NAME, (), 1),
            id="call-missing-reason",
        ),
        pytest.param(
            _Case(Rule.PYR301, "value: tuple[int, str] = (1, 'a')  # pyrigor 301 # API\n", (), _MODULE_NAME),
            id="assignment-same-line",
        ),
        pytest.param(
            _Case(
                Rule.PYR301, "value: tuple[\n    int,  # pyrigor 301 # API\n    str,\n] = (1, 'a')\n", (), _MODULE_NAME
            ),
            id="assignment-middle",
        ),
    ],
)
def test_real_spans_preserve_suppression_boundaries(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], case: _Case, line_break: str
) -> None:
    """The CLI retains exactly the intended findings and emits a schema-valid document."""
    source_file = tmp_path / "matrix.py"
    source_file.write_bytes(case.source.replace("\n", line_break).encode())
    assert main(paths=[str(source_file)], select={case.rule.name}, output_format="json") == int(bool(case.kept))
    captured = capsys.readouterr()
    document: Json = json.loads(captured.out)
    _document_validator().validate(document)
    assert (
        _names(findings=document["findings"]),
        _names(findings=document["suppressed"]),
        len(document["errors"]),
    ) == (
        case.kept,
        case.suppressed,
        case.errors,
    )
    assert bool(captured.err) == bool(case.errors)


def _names(*, findings: list[Json]) -> tuple[str, ...]:
    """Read enclosing identities, so nested findings cannot be confused with their parents."""
    return tuple(finding["enclosing_symbol"]["name"] for finding in findings)


class _ScopeCase(NamedTuple):
    """A canonical subject and the enclosing identity expected from the real CLI."""

    rule: Rule
    source: str
    subject: str
    kind: str
    name: str


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            _ScopeCase(
                Rule.PYR402,
                "class Owner:\n    def flagged(self, a, b):\n        pass\n",
                "Function 'flagged'",
                "method",
                "Owner.flagged",
            ),
            id="method",
        ),
        pytest.param(
            _ScopeCase(
                Rule.PYR402,
                "def outer(*, a, b):\n    def inner(a, b):\n        pass\n",
                "Function 'inner'",
                "function",
                "outer.<locals>.inner",
            ),
            id="nested-function",
        ),
        pytest.param(
            _ScopeCase(
                Rule.PYR406, _CALL_PREFIX + "def outer():\n    compute()\n", "Call 'compute'", "function", "outer"
            ),
            id="call-in-function",
        ),
        pytest.param(
            _ScopeCase(
                Rule.PYR406,
                "class Owner:\n    def value(self) -> int:\n        return 1\n"
                "    def run(self):\n        self.value()\n",
                "Call 'value'",
                "method",
                "Owner.run",
            ),
            id="self-call",
        ),
        pytest.param(
            _ScopeCase(Rule.PYR406, _CALL_PREFIX + "compute()\n", "Call 'compute'", "module", "<module>"),
            id="module-call",
        ),
        pytest.param(
            _ScopeCase(
                Rule.PYR301, "data[0]: tuple[int, str] = (1, 'a')\n", "Variable 'data[0]'", "module", "<module>"
            ),
            id="subscript-target",
        ),
    ],
)
def test_cli_retains_canonical_subjects_and_enclosing_scopes(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], case: _ScopeCase
) -> None:
    """Scope metadata and subject text survive the entire checker-to-document pipeline."""
    source_file = tmp_path / "scope.py"
    source_file.write_text(case.source, encoding="utf-8")
    assert main(paths=[str(source_file)], select={case.rule.name}, output_format="json") == 1
    document: Json = json.loads(capsys.readouterr().out)
    _document_validator().validate(document)
    assert [
        (finding["message"], finding["enclosing_symbol"], finding["fixes"]) for finding in document["findings"]
    ] == [(f"{case.subject} {case.rule.problem}", {"kind": case.kind, "name": case.name}, [])]


@pytest.mark.parametrize("line_break", [b"\n", b"\r\n", b"\r"], ids=["lf", "crlf", "cr"])
@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"], ids=["plain", "bom"])
def test_human_and_json_positions_agree_for_the_same_original_bytes(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], line_break: bytes, bom: bytes
) -> None:
    """BOMs, original newline bytes and a multibyte same-line prefix preserve both position units."""
    source_file = tmp_path / "unicode.py"
    prefix = "label = '\u00e9'; "
    statement = "value: tuple[int, str] = (1, 'a')"
    before = bom + "# \u00e9".encode() + line_break + prefix.encode()
    raw = before + statement.encode() + line_break
    source_file.write_bytes(raw)
    assert main(paths=[str(source_file)], select={Rule.PYR301.name}) == 1
    human = capsys.readouterr().out
    assert human.startswith(f"{source_file}:2:{len(prefix) + 1}: {Rule.PYR301.name} ")
    assert main(paths=[str(source_file)], select={Rule.PYR301.name}, output_format="json") == 1
    document: Json = json.loads(capsys.readouterr().out)
    _document_validator().validate(document)
    span = document["findings"][0]["spans"][0]
    assert (
        span["byte_start"],
        span["byte_end"],
        span["line_start"],
        span["line_end"],
        span["column_start"],
        span["column_end"],
    ) == (len(before), len(before + statement.encode()), 2, 2, len(prefix) + 1, len(prefix + statement) + 1)


def _document_validator() -> Validator:
    """Use the validator protocol so schema calls retain their published input type."""
    return jsonschema.Draft202012Validator(load_v2_schema())


class _RelativePathCase(NamedTuple):
    """An argument spelling, working directory and canonical emitted file name."""

    argument: str
    working_directory: str
    expected: str


@pytest.mark.parametrize(
    "case",
    [
        _RelativePathCase("./source.py", ".", "source.py"),
        _RelativePathCase("child/../source.py", ".", "source.py"),
        _RelativePathCase("../source.py", "child", "../source.py"),
    ],
    ids=["leading-dot", "internal-parent", "leading-parent"],
)
def test_cli_normalises_paths_before_constructing_spans(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, case: _RelativePathCase
) -> None:
    """Normalise redundant segments while preserving the necessary leading parents."""
    argument, working_directory, expected = case
    (tmp_path / "child").mkdir()
    (tmp_path / "source.py").write_text(_FUNCTION, encoding="utf-8")
    monkeypatch.chdir(tmp_path / working_directory)
    assert main(paths=[argument], select={Rule.PYR402.name}, output_format="json") == 1
    document: Json = json.loads(capsys.readouterr().out)
    _document_validator().validate(document)
    assert document["findings"][0]["spans"][0]["file_name"] == expected


@pytest.mark.parametrize("file_name", ["e\u0301tape.py", "\u00e9tape.py"], ids=["decomposed", "composed"])
@pytest.mark.parametrize("suppressed", [False, True], ids=["kept", "suppressed"])
def test_cli_normalises_unicode_file_names_before_emitting_spans(
    *,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    file_name: str,
    suppressed: bool,
) -> None:
    """Both input spellings emit the same NFC path, including enclosing directories."""
    directory = tmp_path / "re\u0301pertoire"
    directory.mkdir()
    source_file = directory / file_name
    prefix = "# pyrigor 402 # deliberate test\n" if suppressed else ""
    source_file.write_bytes((prefix + _FUNCTION).encode())
    monkeypatch.chdir(tmp_path)
    assert main(paths=[str(source_file)], select={Rule.PYR402.name}, output_format="json") == int(not suppressed)
    document: Json = json.loads(capsys.readouterr().out)
    _document_validator().validate(document)
    findings = document["suppressed"] if suppressed else document["findings"]
    assert (findings[0]["spans"][0]["file_name"], document["summary"]["files_checked"]) == (
        "r\u00e9pertoire/\u00e9tape.py",
        1,
    )


class _FixLayout(NamedTuple):
    """The original newline bytes, optional BOM and CLI operation."""

    line_break: bytes
    bom: bytes
    option: str


@pytest.mark.parametrize(
    "layout",
    [_FixLayout(*values) for values in product([b"\n", b"\r\n", b"\r"], [b"", b"\xef\xbb\xbf"], ["--fix", "--diff"])],
)
@pytest.mark.parametrize("signature_comment", [False, True], ids=["body-comment", "signature-comment"])
def test_fix_and_diff_use_the_same_signature_suppression_boundaries(
    *,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    layout: _FixLayout,
    signature_comment: bool,
) -> None:
    """Signature suppression prevents edits; body suppression does not, under every byte layout."""
    comment = "# pyrigor 402 # deliberate test"
    lines = (
        [comment, "def flagged(a, b):", "    pass"]
        if signature_comment
        else ["def flagged(a, b):", "    " + comment, "    pass"]
    )
    original = layout.bom + layout.line_break.join(line.encode() for line in lines) + layout.line_break
    source_file = tmp_path / "source.py"
    source_file.write_bytes(original)
    monkeypatch.setattr(sys, "argv", ["pyrigor", layout.option, "--select=PYR402", str(source_file)])
    with pytest.raises(SystemExit) as caught:
        run()
    captured = capsys.readouterr()
    fixed = original if signature_comment else original.replace(b"def flagged(a, b):", b"def flagged(*, a, b):")
    expected = {"--fix": fixed, "--diff": original}[layout.option]
    marker = {"--fix": f"Fixed {source_file}\n", "--diff": "+def flagged(*, a, b):"}[layout.option]
    assert (caught.value.code, captured.err, source_file.read_bytes(), bool(captured.out), marker in captured.out) == (
        0,
        "",
        expected,
        not signature_comment,
        not signature_comment,
    )
