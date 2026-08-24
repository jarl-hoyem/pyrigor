"""Generates guidelines/'RULES.md' from the real guideline docs and CHECKERS.

Real drift found before this existed: PYR404 still showed "Rejected, see
REJECTED.md" after being renumbered to PYREJECT101. PYR502's one-liner
described the rejected assert-based approach, not the actual raise-based
rule. PYR206/PYR303/PYR503 were missing from the table entirely. A hand-maintained
table cannot avoid this. Scanning the real files can.

Regenerates the file, then fails the commit if it changed -- the same
pattern as version_sync.py -- forcing the diff to be staged rather than
silently trusting the script was run.
"""

import re
import subprocess  # nosec -- fixed, local tooling commands only
import sys
from pathlib import Path
from typing import NamedTuple

from pyrigor.checkers import CHECKERS

_GUIDELINES_DIR = Path("guidelines")
_OUTPUT_PATH = _GUIDELINES_DIR / "RULES.md"
_RULE_FILENAME_PATTERN = re.compile(r"^(?P<rule_id>PYR\d+)-")
_TITLE_LINE_PATTERN = re.compile(r"^#\s*PYR\d+\s*[—-]\s*(?P<title>.+)$")


class RuleRow(NamedTuple):
    """One row of the generated rule table."""

    rule_id: str
    title: str
    enforced_by: str


def _rule_id_from_filename(*, path: Path) -> str | None:
    """Extract a rule ID like "PYR201" from a guideline doc's filename.

    Args:
        path: A file under guidelines/.

    Returns:
        The rule ID, or None if the filename does not match a real rule
        doc (the template, or something else entirely).
    """
    match = _RULE_FILENAME_PATTERN.match(path.name)
    return match.group("rule_id") if match else None


def _title_from_file(*, path: Path) -> str:
    """Extract a rule doc's own one-line title from its first heading.

    Args:
        path: The guideline doc to read.

    Returns:
        The title text after the rule ID and dash on the file's
        first line.
    """
    first_line = path.read_text(encoding="utf-8").splitlines()[0]
    match = _TITLE_LINE_PATTERN.match(first_line)
    if match is None:
        raise ValueError(f"{path}: first line does not match the expected '# PYRxxx — Title' heading")
    return match.group("title")


def _enforced_rule_names() -> set[str]:
    """Get every rule name actually registered in CHECKERS.

    Returns:
        The set of enforced rule codes, for example {"PYR301", "PYR401"}.
    """
    return {entry.rule.name for entry in CHECKERS}


def _collect_rows() -> list[RuleRow]:
    """Collect one row per real guideline doc found under guidelines/.

    Returns:
        Rows sorted by rule ID (filename sort order already matches,
        since every rule number is zero-padded to three digits).
    """
    enforced = _enforced_rule_names()
    rows = []
    for path in sorted(_GUIDELINES_DIR.glob("PYR*.md")):
        rule_id = _rule_id_from_filename(path=path)
        if rule_id is None:
            continue
        title = _title_from_file(path=path)
        enforced_by = "`pyrigor` CLI (pre-commit hook)" if rule_id in enforced else "Not yet implemented"
        rows.append(RuleRow(rule_id=rule_id, title=title, enforced_by=enforced_by))
    return rows


def _render_row(*, row: RuleRow, id_width: int, title_width: int, enforced_width: int) -> str:
    """Render one row (or the header, also expressed as a RuleRow), padded to fixed column widths.

    Args:
        row: The row to render.
        id_width: The ID column's target width.
        title_width: The Rule column's target width.
        enforced_width: The Enforced by the column's target width.

    Returns:
        One column-aligned Markdown table row.
    """
    return (
        f"| {row.rule_id.ljust(id_width)} | {row.title.ljust(title_width)} | {row.enforced_by.ljust(enforced_width)} |"
    )


def _render_table(*, rows: list[RuleRow]) -> str:
    """Render the collected rows as a column-aligned GitHub-flavored Markdown table.

    Args:
        rows: Already-sorted rule rows.

    Returns:
        The full table as Markdown text, including the header row, with
        every column padded to a consistent width, so the raw file reads
        as a real, aligned table, not just valid-but-ragged markup.
    """
    header = RuleRow(rule_id="ID", title="Rule", enforced_by="Enforced by")
    all_rows = [header, *rows]
    id_width = max(len(row.rule_id) for row in all_rows)
    title_width = max(len(row.title) for row in all_rows)
    enforced_width = max(len(row.enforced_by) for row in all_rows)

    separator = f"|{'-' * (id_width + 2)}|{'-' * (title_width + 2)}|{'-' * (enforced_width + 2)}|"
    lines = [
        _render_row(row=header, id_width=id_width, title_width=title_width, enforced_width=enforced_width),
        separator,
    ]
    lines.extend(
        _render_row(row=row, id_width=id_width, title_width=title_width, enforced_width=enforced_width) for row in rows
    )
    return "\n".join(lines)


def _render_file(*, table: str) -> str:
    """Wrap the generated table with a header explaining it is generated.

    Args:
        table: The rendered Markdown table.

    Returns:
        The full file content to write.
    """
    return (
        "# Rules\n\n"
        "Generated from `guidelines/PYR*.md` and `pyrigor.checkers.CHECKERS`\n"
        "by `scripts/generate_rule_table.py` -- do not edit this file by\n"
        "hand, it is overwritten on the next commit. See each rule's own\n"
        "guideline doc for its full rationale.\n\n"
        f"{table}\n"
    )


def main() -> None:
    """Regenerate guidelines/RULES.md, then fail if it changed, so the diff gets staged."""
    rows = _collect_rows()
    content = _render_file(table=_render_table(rows=rows))
    _OUTPUT_PATH.write_text(content, encoding="utf-8")

    # noinspection PyArgumentEqualDefault
    result = subprocess.run(  # nosec # noqa: S603 -- fixed args, _OUTPUT_PATH is a module constant, not user input
        ["git", "diff", "--name-only", "--", str(_OUTPUT_PATH)],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.stdout.strip():
        print(f"{_OUTPUT_PATH} regenerated and changed. Re-stage it and commit again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
