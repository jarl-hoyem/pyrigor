#!/usr/bin/env python3

"""Block Claude from reading files larger than 350 lines in one operation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

MAX_LINES = 350
_TARGETED_READ_KEYS = ("offset", "limit")


def _is_targeted_read(*, tool_input: dict[str, object]) -> bool:
    """Return whether the read already limits how much of the file it takes."""
    return any(key in tool_input for key in _TARGETED_READ_KEYS)


def _line_count(*, path: Path) -> int | None:
    """Count a file's lines or return None when it cannot be read as text.

    Claude's Read tool then reports the real error and handles a file that is not text at all.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    return content.count("\n")


def _denial(*, line_count: int) -> str:
    """Build the hook's answer denying one oversized read."""
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"This file has {line_count} lines, exceeding the "
                    f"{MAX_LINES}-line direct-read limit. "
                    "Do not read the entire file. Use targeted reads with "
                    "offset/limit, or use an appropriate large-file reader."
                ),
            }
        }
    )


def _oversized_lines(*, tool_input: dict[str, object]) -> int | None:
    """Return the line count of a read that must be denied, or None when the read may proceed."""
    file_path = tool_input.get("file_path")
    if not file_path or _is_targeted_read(tool_input=tool_input):
        return None

    line_count = _line_count(path=Path(str(file_path)))
    if line_count is None or line_count <= MAX_LINES:
        return None
    return line_count


def main() -> None:
    """Check a Claude Read request and block an oversized read."""
    try:
        request = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return

    line_count = _oversized_lines(tool_input=request.get("tool_input", {}))
    if line_count is not None:
        sys.stdout.write(_denial(line_count=line_count))
        sys.exit(2)


if __name__ == "__main__":
    main()
