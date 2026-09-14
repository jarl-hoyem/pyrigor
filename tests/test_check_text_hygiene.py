"""Tests for the text-hygiene pre-commit checker."""
# pylint: disable=duplicate-code  # Independent subprocess setup is deliberate in this test module.
# pylint: disable=magic-value-comparison

import subprocess  # nosec B404 -- test invokes a fixed local checker script
import sys
from pathlib import Path


def _run_checker(*, tmp_path: Path, data: bytes) -> list[str]:
    """Run the checker script against temporary content."""
    source = tmp_path / "sample.txt"
    source.write_bytes(data)

    # Try the relative path first, which is the normal pytest run.
    checker_path = Path(__file__).parents[1] / "scripts" / "check_text_hygiene.py"

    # If it is not found, the run is probably inside mutants/. Search parent directories for scripts/.
    if not checker_path.exists():
        for parent in Path(__file__).parents[1].parents:
            candidate = parent / "scripts" / "check_text_hygiene.py"
            if candidate.exists():
                checker_path = candidate
                break

    # noinspection PyArgumentEqualDefault
    result = subprocess.run(  # nosec B603 -- executes the repository's fixed checker script # noqa: S603
        [sys.executable, str(checker_path), str(source)],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.splitlines()


def test_accepts_clean_ascii_and_intentional_unicode(*, tmp_path: Path) -> None:
    """Normal source text and intentional Unicode are accepted."""
    source = ("c" + "af" + chr(0xE9) + " = '" + chr(0x1F8) + "'\n").encode()
    assert _run_checker(tmp_path=tmp_path, data=source) == []


def test_rejects_control_and_terminal_escape_characters(*, tmp_path: Path) -> None:
    """C0 controls and terminal escapes are rejected."""
    issues = _run_checker(tmp_path=tmp_path, data=b"good\n\x1b[31mred\x1b[0m\x00\n")

    assert len(issues) == 3
    assert "U+001B" in issues[0]
    assert "U+0000" in issues[2]


def test_rejects_replacement_character(*, tmp_path: Path) -> None:
    """The Unicode replacement character is rejected."""
    issues = _run_checker(tmp_path=tmp_path, data=("bad " + chr(0xFFFD) + " text\n").encode())

    assert len(issues) == 1
    assert "U+FFFD" in issues[0]


def test_rejects_common_mojibake_markers(*, tmp_path: Path) -> None:
    """Common mojibake marker characters are rejected."""
    mojibake = " ".join(chr(codepoint) for codepoint in (0xE2, 0xC2, 0xC3, 0xF0))
    issues = _run_checker(tmp_path=tmp_path, data=(mojibake + "\n").encode())

    assert len(issues) == 4
    assert all("mojibake marker" in issue for issue in issues)


def test_rejects_invalid_utf8_as_binary_text(*, tmp_path: Path) -> None:
    """Invalid UTF-8 is rejected instead of being silently decoded."""
    issues = _run_checker(tmp_path=tmp_path, data=b"valid\xff\n")

    assert issues == [f"{tmp_path / 'sample.txt'}: invalid UTF-8"]


def test_accepts_straight_apostrophes_and_quotation_marks(*, tmp_path: Path) -> None:
    """Straight apostrophes and quotation marks pass, in prose and in code."""
    source = b"It's \"quoted\" prose, and `value = 'text'` in code.\n"
    assert _run_checker(tmp_path=tmp_path, data=source) == []


def test_accepts_text_without_any_quotation_marks(*, tmp_path: Path) -> None:
    """A file with no apostrophes or quotation marks at all has nothing to report."""
    assert _run_checker(tmp_path=tmp_path, data=b"plain text\n") == []


def test_rejects_each_curly_quotation_mark(*, tmp_path: Path) -> None:
    """All four curly forms are rejected, one issue per character, in order."""
    codes = ("U+2018", "U+2019", "U+201C", "U+201D")
    curly = chr(0x2018) + " " + chr(0x2019) + " " + chr(0x201C) + " " + chr(0x201D)
    issues = _run_checker(tmp_path=tmp_path, data=(curly + "\n").encode())

    assert len(issues) == len(codes)
    assert all(code in issue and "curly quotation mark" in issue for code, issue in zip(codes, issues, strict=True))


def test_rejects_curly_apostrophe_inside_fenced_code(*, tmp_path: Path) -> None:
    """The rule is unconditional, so a fenced code block does not exempt a curly apostrophe."""
    source = ("```python\nname = 'it" + chr(0x2019) + "s'\n```\n").encode()
    issues = _run_checker(tmp_path=tmp_path, data=source)

    assert len(issues) == 1
    assert "U+2019" in issues[0]
