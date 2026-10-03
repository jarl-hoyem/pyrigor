"""Check, before any file is read, that every path has a file name the v2 schema accepts."""

import os
import re
import shutil
import string
import sys
import tempfile
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple
from unittest.mock import patch

import pytest

from pyrigor.checkers.cli import run
from pyrigor.diagnostics import DiagnosticInputError, require_representable_file_name
from pyrigor.findings import FileName
from tests.diagnostics_v2_support import definition_validator, load_v2_schema

_USAGE_ERROR = 2
_CRASH_MESSAGE = "pyrigor crashed unexpectedly"
_EXCLUDE = "--exclude"
_CODE_POINT = "U+034F"
_GOOD_FILE = "a_good.py"
_RELATIVE_RULE = "relative path with forward slashes"
_DRIVE_ADVICE = "run from the file's drive"
_SKIP_WARNING = "Warning: skipping"
_BACKSLASH = chr(0x5C)
_GRAPHEME_JOINER = chr(0x34F)
_WINDOWS_NAME = "nt"
_WINDOWS = os.name == _WINDOWS_NAME
_SURROGATES = range(0xD800, 0xE000)
_FINDING_SOURCE = "def flagged(a, b): pass\n"
_PARSE_ERROR_SOURCE = "def broken(: pass\n"

_CHARACTER_RULES = (
    "No control characters.",
    "No zero-width, bidirectional control or byte-order mark characters.",
    "No invisible filler, joiner or annotation characters.",
)
_STRUCTURAL_VIOLATORS = {
    "Relative, so not starting with a slash or a drive letter.": ["/a.py", "C:a.py", "c:/a.py"],
    "Forward slashes only.": [f"dir{_BACKSLASH}a.py", f"{_BACKSLASH}a.py"],
    "No empty segment, and no trailing slash.": ["a//b.py", "a/b/"],
    "A parent-directory segment only at the start, then an ordinary segment.": ["a/../b.py", "..", "../.."],
    "No current-directory segment.": ["./a.py", "a/./b.py"],
    "No segment starts or ends with whitespace.": [" a.py", "a.py ", "a/ b.py", "a /b.py"],
}
_ACCEPTED_NAMES = [
    "a.py",
    "dir/a.py",
    "../a.py",
    "../../dir/a.py",
    "report:2024.py",
    "ab:c.py",
    "a b.py",
    "dir name/a b.py",
    "\u00e9.py",
    f"{chr(0x20000)}.py",
]


class _Outcome(NamedTuple):
    """The exit code and both output streams of one run."""

    code: object
    out: str
    err: str


def _run_cli(
    *,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str],
) -> _Outcome:
    """Run the console entry point with the arguments and collect what it did."""
    monkeypatch.setattr(sys, "argv", ["pyrigor", *arguments])
    with pytest.raises(SystemExit) as caught:
        run()
    captured = capsys.readouterr()
    return _Outcome(code=caught.value.code, out=captured.out, err=captured.err.replace("\\\\", "\\"))


def _schema_rules() -> dict[str, str]:
    """Map each rule of the schema's file name to its pattern."""
    return {part["description"]: part["pattern"] for part in load_v2_schema()["$defs"]["FileName"]["allOf"]}


def _forbidden_names(*, rule: str) -> list[str]:
    """Build one name per character a character rule of the schema forbids, taken from its own pattern."""
    forbidden_class = _schema_rules()[rule].removeprefix("^(?![\\s\\S]*").removesuffix(")")
    every_character = "".join(chr(code_point) for code_point in range(0x110000) if code_point not in _SURROGATES)
    return [f"a{character}b.py" for character in re.findall(forbidden_class, every_character)]


def test_the_checked_rules_are_exactly_the_rules_of_the_schema() -> None:
    """A rule added to the schema's file name fails here until the check and this list cover it."""
    assert set(_schema_rules()) == {*_CHARACTER_RULES, *_STRUCTURAL_VIOLATORS}


@pytest.mark.parametrize("rule", [*_CHARACTER_RULES, *_STRUCTURAL_VIOLATORS])
def test_every_name_a_schema_rule_rejects_is_rejected(*, rule: str) -> None:
    """The check rejects what the schema rejects, character by character for the character rules."""
    names = _STRUCTURAL_VIOLATORS[rule] if rule in _STRUCTURAL_VIOLATORS else _forbidden_names(rule=rule)
    assert names
    validator = definition_validator(definition="FileName")
    for name in names:
        assert not validator.is_valid(name), name
        with pytest.raises(DiagnosticInputError):
            require_representable_file_name(file_name=FileName(name), path="x.py")


@pytest.mark.parametrize("name", _ACCEPTED_NAMES)
def test_a_name_the_schema_accepts_is_accepted(*, name: str) -> None:
    """The check does not reject a name that the schema accepts."""
    assert definition_validator(definition="FileName").is_valid(name)
    require_representable_file_name(file_name=FileName(name), path="x.py")


def test_a_name_that_is_not_valid_unicode_is_rejected() -> None:
    """A file name holding undecodable bytes reaches Python as a lone surrogate."""
    with pytest.raises(DiagnosticInputError, match="lone surrogate"):
        require_representable_file_name(file_name=FileName("a" + chr(0xD800) + ".py"), path="x.py")


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("dir/ a.py", "file_name has a segment that starts or ends with whitespace"),
        ("a//b.py", "file_name has an empty, current-directory or misplaced parent-directory segment"),
        ("a:b.py", "file_name must be a relative path with forward slashes"),
        (f"a{chr(0xD800)}.py", "file_name contains a lone surrogate"),
        (f"a{_GRAPHEME_JOINER}.py", "the file name contains U+034F, which the current v2 producer cannot represent"),
    ],
    ids=["whitespace", "segment", "relative", "surrogate", "invisible"],
)
def test_the_message_names_the_path_the_rule_and_the_way_to_skip_the_file(*, name: str, reason: str) -> None:
    """The user learns which file, why it was refused and how to carry on."""
    with pytest.raises(DiagnosticInputError) as caught:
        require_representable_file_name(file_name=FileName(name), path="dir/file.py")
    assert str(caught.value) == f"'dir/file.py': {reason}; use --exclude to skip this file"


@pytest.mark.parametrize("output_format", ["human", "json"])
def test_a_bad_name_under_a_directory_stops_the_run_before_any_file_is_read(
    *,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    output_format: str,
) -> None:
    """A good file read before the bad name was reached would show as a read, not as the usage error."""
    (tmp_path / "a_good.py").write_text(_FINDING_SOURCE, encoding="utf-8")
    bad = tmp_path / f"z_bad{_GRAPHEME_JOINER}.py"
    bad.write_text(_FINDING_SOURCE, encoding="utf-8")
    with patch.object(Path, "read_bytes", side_effect=AssertionError("no file may be read")):
        outcome = _run_cli(
            monkeypatch=monkeypatch,
            capsys=capsys,
            arguments=[f"--output-format={output_format}", str(tmp_path)],
        )
    observed = (
        outcome.code,
        outcome.out,
        _CODE_POINT in outcome.err,
        _EXCLUDE in outcome.err,
        str(bad) in outcome.err,
        _CRASH_MESSAGE in outcome.err,
    )
    assert observed == (_USAGE_ERROR, "", True, True, True, False)


def test_excluding_the_bad_file_lets_the_run_report_the_others(
    *,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The advice in the message works."""
    good = tmp_path / "a_good.py"
    good.write_text(_FINDING_SOURCE, encoding="utf-8")
    bad = tmp_path / f"z_bad{_GRAPHEME_JOINER}.py"
    bad.write_text(_FINDING_SOURCE, encoding="utf-8")
    outcome = _run_cli(monkeypatch=monkeypatch, capsys=capsys, arguments=[f"--exclude={bad}", str(tmp_path)])
    assert (outcome.code, _GOOD_FILE in outcome.out, outcome.err) == (1, True, "")


@pytest.mark.parametrize("source", [_FINDING_SOURCE, _PARSE_ERROR_SOURCE], ids=["finding", "parse-error"])
@pytest.mark.parametrize("output_format", ["human", "json"])
def test_a_name_with_a_drive_letter_is_a_usage_error_for_findings_and_errors(
    *,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    output_format: str,
) -> None:
    """On POSIX such a name reaches the document, as a crash for a finding and as an invalid error entry."""
    path = tmp_path / "real.py"
    path.write_text(source, encoding="utf-8")
    with patch("pyrigor.checkers.cli.os.path.relpath", return_value="a:b.py"):
        outcome = _run_cli(
            monkeypatch=monkeypatch,
            capsys=capsys,
            arguments=[f"--output-format={output_format}", str(path)],
        )
    observed = (
        outcome.code,
        outcome.out,
        _RELATIVE_RULE in outcome.err,
        _EXCLUDE in outcome.err,
        _CRASH_MESSAGE in outcome.err,
    )
    assert observed == (_USAGE_ERROR, "", True, True, False)


@pytest.mark.skipif(_WINDOWS, reason="Windows cannot create these file names")
@pytest.mark.parametrize("name", [f"x{_BACKSLASH}y.py", "a:b.py"], ids=["backslash", "letter-and-colon"])
@pytest.mark.parametrize("output_format", ["human", "json"])
def test_a_real_posix_file_name_the_schema_rejects_stops_the_run(
    *,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    output_format: str,
) -> None:
    """The names are legal on Linux and macOS, so a real file can carry them."""
    (tmp_path / name).write_text(_FINDING_SOURCE, encoding="utf-8")
    outcome = _run_cli(
        monkeypatch=monkeypatch,
        capsys=capsys,
        arguments=[f"--output-format={output_format}", str(tmp_path)],
    )
    observed = (outcome.code, outcome.out, _EXCLUDE in outcome.err, _CRASH_MESSAGE in outcome.err)
    assert observed == (_USAGE_ERROR, "", True, False)


def _current_drive() -> str:
    """Return the drive letter of the working directory."""
    return Path.cwd().drive[0].upper()


def _another_drive() -> str:
    """Return a drive letter other than the working directory's, whether it exists."""
    return next(letter for letter in string.ascii_uppercase[::-1] if letter != _current_drive())


@pytest.mark.skipif(not _WINDOWS, reason="Only Windows has drives, UNC paths and extended-length paths")
@pytest.mark.parametrize(
    "path",
    [
        lambda: f"{_another_drive()}:a.py",
        lambda: f"{_another_drive()}:{_BACKSLASH}a.py",
        lambda: f"{_BACKSLASH}{_BACKSLASH}server{_BACKSLASH}share{_BACKSLASH}a.py",
        lambda: f"{_BACKSLASH}{_BACKSLASH}?{_BACKSLASH}{_another_drive()}:{_BACKSLASH}a.py",
        lambda: f"{_BACKSLASH}{_BACKSLASH}?{_BACKSLASH}{Path.cwd()}{_BACKSLASH}a.py",
    ],
    ids=["drive-relative-other-drive", "absolute-other-drive", "unc", "extended-length-other-drive", "extended-length"],
)
@pytest.mark.parametrize("output_format", ["human", "json"])
def test_windows_paths_without_a_relative_form_are_a_usage_error(
    *,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    path: Callable[[], str],
    output_format: str,
) -> None:
    """An extended-length path has no relative form even on the working directory's own drive."""
    outcome = _run_cli(monkeypatch=monkeypatch, capsys=capsys, arguments=[f"--output-format={output_format}", path()])
    observed = (outcome.code, outcome.out, _DRIVE_ADVICE in outcome.err, _CRASH_MESSAGE in outcome.err)
    assert observed == (_USAGE_ERROR, "", True, False)


@pytest.mark.skipif(not _WINDOWS, reason="Only Windows has drive letters")
def test_a_drive_relative_path_on_the_current_drive_has_a_relative_form(
    *,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D: a.py means a.py in the working directory of drive D, so on the current drive it is an ordinary name."""
    outcome = _run_cli(monkeypatch=monkeypatch, capsys=capsys, arguments=[f"{_current_drive()}:missing_345.py"])
    assert (outcome.code, _SKIP_WARNING in outcome.err, _CRASH_MESSAGE in outcome.err) == (0, True, False)


def _second_drive_roots() -> list[str]:
    """List the places to try on drives other than the working directory's, the temporary directory first."""
    candidates = [tempfile.gettempdir(), *(f"{letter}:{_BACKSLASH}" for letter in string.ascii_uppercase)]
    return [root for root in candidates if Path(root).drive[:1].upper() not in {"", _current_drive()}]


def _try_to_make_directory(*, root: str) -> Path | None:
    """Create a temporary directory under the root or return None when the root is not writable."""
    try:
        return Path(tempfile.mkdtemp(dir=root))
    except OSError:
        return None


def _make_second_drive_directory() -> Path | None:
    """Create a temporary directory on another drive or return None when no drive accepts one."""
    for root in _second_drive_roots():
        directory = _try_to_make_directory(root=root)
        if directory is not None:
            return directory
    return None


@contextmanager
def _second_drive_directory() -> Generator[Path]:
    """Provide a temporary directory on a drive other than the working directory's, or skip the test."""
    if not _WINDOWS:
        pytest.skip("Only Windows has drives")
    directory = _make_second_drive_directory()
    if directory is None:
        pytest.skip("No writable second drive")
    try:
        yield directory
    finally:
        shutil.rmtree(directory, ignore_errors=True)


@pytest.mark.parametrize("output_format", ["human", "json"])
def test_a_real_file_on_a_second_drive_is_a_usage_error(
    *,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    output_format: str,
) -> None:
    """A real checkout on another drive, as on the Windows CI runner, has no relative form."""
    with _second_drive_directory() as directory:
        path = directory / "other_drive.py"
        path.write_text(_FINDING_SOURCE, encoding="utf-8")
        outcome = _run_cli(
            monkeypatch=monkeypatch,
            capsys=capsys,
            arguments=[f"--output-format={output_format}", str(path)],
        )
    observed = (outcome.code, outcome.out, _DRIVE_ADVICE in outcome.err, _CRASH_MESSAGE in outcome.err)
    assert observed == (_USAGE_ERROR, "", True, False)
