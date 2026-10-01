"""Block an Edit or Write that introduces a new suppression comment.

A context reminder is not enough: the agent has repeatedly added a suppression (a pylint disable comment, a
type: ignore, a noqa, a noinspection, or pyrigor's own suppression syntax) without first asking.
AGENTS.md requires its own explicit go-ahead for every suppression, separate from the approval of the
surrounding diff. This hook makes that a hard gate instead of a reminder the agent can miss.

Only newly added lines are checked, so an existing suppression already in the file never blocks an
unrelated edit.
"""

from __future__ import annotations

import json
import re
import sys

from hook_shared import OldAndNewText, added_lines, deny_if, is_within_repo, old_and_new_text, repo_root

_SUPPRESSION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"#\s*pylint\s*:\s*disable", re.IGNORECASE),
    re.compile(r"#\s*noqa\b", re.IGNORECASE),
    re.compile(r"#\s*type\s*:\s*ignore", re.IGNORECASE),
    re.compile(r"#\s*noinspection\b", re.IGNORECASE),
    re.compile(r"#\s*pyrigor\s+\S+.*#", re.IGNORECASE),
)

_REPO_ROOT = repo_root(hook_file=__file__)


def _new_suppressions(*, old_text: str, new_text: str) -> list[str]:
    """Return the newly added lines that contain a suppression comment."""
    return [
        line.strip()
        for line in added_lines(old_text=old_text, new_text=new_text)
        if any(pattern.search(line) for pattern in _SUPPRESSION_PATTERNS)
    ]


def _deny_reason(*, hits: list[str]) -> str | None:
    """Return the reason to deny this edit, or None when there is nothing to deny."""
    if not hits:
        return None
    examples = "; ".join(hits[:5])
    return (
        f"This edit adds a new suppression comment not present in the original text: {examples}. "
        "AGENTS.md requires its own explicit, separate approval before adding a suppression "
        "(pylint disable, noqa, type: ignore, noinspection, or pyrigor's own "
        "'# pyrigor CODE # reason'). Stop. Try a real fix first. If a suppression is genuinely "
        "the right answer, show the user the finding, the reason a direct fix was not done, "
        "and the exact reason text the suppression will carry, then wait for an explicit "
        "go-ahead before retrying this edit."
    )


def main() -> None:
    """Check an Edit or Write request and block one that adds a new suppression comment."""
    try:
        request = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return

    tool_name = request.get("tool_name")
    if tool_name not in ("Edit", "Write"):
        return

    tool_input = request.get("tool_input", {})
    if not is_within_repo(file_path=str(tool_input.get("file_path", "")), root=_REPO_ROOT):
        return

    old_new: OldAndNewText = old_and_new_text(tool_name=tool_name, tool_input=tool_input)
    hits = _new_suppressions(old_text=old_new.old, new_text=old_new.new)
    deny_if(reason=_deny_reason(hits=hits))


if __name__ == "__main__":
    main()
