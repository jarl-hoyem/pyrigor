"""Shared helpers for pyrigor's house-style PreToolUse hooks.

Not a hook itself. check_new_suppressions.py and check_british_spelling.py both import from here, so
the diffing and repo-scoping logic they share lives in one place instead of twice, the shape pylint's
duplicate-code check flagged.
"""

from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path
from typing import NamedTuple

_EDIT_TOOL_NAME = "Edit"
_REPLACED_OPCODES = {"insert", "replace"}


class OldAndNewText(NamedTuple):
    """The before and after text an Edit or Write would produce."""

    old: str
    new: str


def repo_root(*, hook_file: str) -> Path:
    """Return the repository root, given one hook script's own __file__."""
    return Path(hook_file).resolve().parents[2]


def is_within_repo(*, file_path: str, root: Path) -> bool:
    """Return whether file_path lies inside the root.

    A hook only governs pyrigor's own house rules, so a tool call touching any other path, such as a
    memory file or a scratch file elsewhere on disk, is left alone.
    """
    if not file_path:
        return False
    try:
        resolved = Path(file_path).resolve()
    except OSError:
        return False
    return resolved == root or root in resolved.parents


def old_and_new_text(*, tool_name: str, tool_input: dict[str, object]) -> OldAndNewText:
    """Return the before and after text an Edit or Write would produce.

    For a Write to an existing file, the before text is read from disk, since a PreToolUse hook runs
    before the tool call and the file on disk is still the old version.
    """
    if tool_name == _EDIT_TOOL_NAME:
        return OldAndNewText(old=str(tool_input.get("old_string", "")), new=str(tool_input.get("new_string", "")))

    new_text = str(tool_input.get("content", ""))
    file_path = tool_input.get("file_path")
    if not file_path:
        return OldAndNewText(old="", new=new_text)
    try:
        old_text = Path(str(file_path)).read_text(encoding="utf-8")
    except OSError:
        old_text = ""
    return OldAndNewText(old=old_text, new=new_text)


def added_lines(*, old_text: str, new_text: str) -> list[str]:
    """Return the lines present in new_text that were not present in old_text.

    Uses sequence alignment rather than a set difference, so a line that only moved position is not
    mistaken for a newly added one.
    """
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    added: list[str] = []
    for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
        if tag in _REPLACED_OPCODES:
            added.extend(new_lines[j1:j2])
    return added


def deny(*, reason: str) -> str:
    """Build a PreToolUse hook's hard-deny JSON response."""
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
    )


def deny_if(*, reason: str | None) -> None:
    """Write a hard-deny response and exit nonzero when the reason is not None.

    Does nothing otherwise, letting the tool call proceed.
    """
    if reason is None:
        return
    sys.stdout.write(deny(reason=reason))
    sys.exit(2)
