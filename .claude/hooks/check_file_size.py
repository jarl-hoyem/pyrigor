#!/usr/bin/env python3

"""Block Claude from reading files larger than 350 lines in one operation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

MAX_LINES = 350


def main() -> None:
    """Check a Claude Read request and block oversized reads."""
    try:
        request = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return

    tool_input = request.get("tool_input", {})
    file_path = tool_input.get("file_path")

    if not file_path:
        return

    # Targeted reads using offset/limit are allowed.
    if "offset" in tool_input or "limit" in tool_input:
        return

    path = Path(file_path)

    try:
        line_count = sum(1 for _ in path.open(encoding="utf-8"))
    except (OSError, UnicodeError):
        # Let Claude's Read tool report the actual error.
        return

    if line_count <= MAX_LINES:
        return

    result = {
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

    print(json.dumps(result))


if __name__ == "__main__":
    main()