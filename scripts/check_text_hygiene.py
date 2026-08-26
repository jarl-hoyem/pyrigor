"""Reject terminal-control characters and common mojibake in text files."""

import sys
from pathlib import Path

_MOJIBAKE_MARKERS = frozenset("\u00e2\u00c2\u00c3\u00f0")
_REPLACEMENT_CODEPOINT = 0xFFFD
_C0_LIMIT = 32
_DEL_CODEPOINT = 0x7F
_C1_LIMIT = 0x9F
_ALLOWED_CONTROLS = "\t\n\r"


def find_text_hygiene_issues(*, data: bytes) -> list[str]:
    """Return descriptions of suspicious characters in UTF-8 data."""
    try:
        text = data.decode()
    except UnicodeDecodeError:
        return ["invalid UTF-8"]
    issues: list[str] = []
    for character in text:
        issue = _character_issue(character=character)
        if issue is not None:
            issues.append(issue)
    return issues


def _character_issue(*, character: str) -> str | None:
    """Return a hygiene issue for one character, if any."""
    control_issue = _control_issue(character=character)
    if control_issue is not None:
        return control_issue
    if ord(character) == _REPLACEMENT_CODEPOINT:
        return "U+FFFD replacement character"
    if character in _MOJIBAKE_MARKERS:
        return f"{character} mojibake marker"
    return None


def _control_issue(*, character: str) -> str | None:
    """Return a control-character issue if the character is unsafe."""
    codepoint = ord(character)
    if (codepoint < _C0_LIMIT and character not in _ALLOWED_CONTROLS) or _DEL_CODEPOINT <= codepoint <= _C1_LIMIT:
        return f"U+{codepoint:04X} control character"
    return None


def main() -> int:
    """Check the filenames supplied by pre-commit."""
    failed = False
    for filename in sys.argv[1:]:
        path = Path(filename)
        issues = find_text_hygiene_issues(data=path.read_bytes())
        for issue in issues:
            print(f"{path}: {issue}")
        failed = failed or bool(issues)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
