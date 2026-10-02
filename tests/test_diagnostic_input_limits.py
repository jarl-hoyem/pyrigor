"""Make temporary producer limits explicit instead of emitting invalid v2 documents."""

import sys
from pathlib import Path
from typing import NamedTuple
from unittest.mock import patch

import pytest

from pyrigor.checkers.cli import run
from pyrigor.diagnostics import require_supported_findings
from pyrigor.rules import Rule
from tests.checker_helpers import finding_at

_USAGE_ERROR = 2
_RELATIVE_FRAGMENT = "relative"
_REJECTED_CODE_POINTS = [0x034F, 0x115F, 0x1160, 0x200C, 0x200D]


class _RejectedCase(NamedTuple):
    """One affected identifier and the field that will carry it."""

    code_point: int
    rule: Rule
    template: str


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
