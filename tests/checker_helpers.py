"""Build a source context once for checker tests."""

import ast
from collections.abc import Callable

from pyrigor.checkers import walk_once
from pyrigor.finding_builder import FindingContext
from pyrigor.findings import ByteOffset, ColumnNumber, FileName, Finding, LineNumber, PositionIndex, Span
from pyrigor.rules import Rule


def check_source(*, source: str, checker: Callable[..., list[Finding]]) -> list[Finding]:
    """Parse and walk the source, then check it with its source positions."""
    raw = source.encode()
    normalised = source.replace("\r\n", "\n").replace("\r", "\n")
    nodes = walk_once(tree=ast.parse(normalised))
    context = FindingContext(
        source=normalised,
        index=PositionIndex(raw=raw),
        file_name=FileName("test.py"),
        parents=nodes.parents,
    )
    return checker(nodes=nodes, context=context)


def finding_at(*, line: int, end_line: int, column: int, rule: Rule, end_column: int | None = None) -> Finding:
    """Build synthetic positions for comment and ordering tests, independently of source indexing."""
    return Finding(
        code=rule,
        message="Function 'x' " + rule.problem,
        spans=(
            Span(
                file_name=FileName("test.py"),
                byte_start=ByteOffset(0),
                byte_end=ByteOffset(0),
                line_start=LineNumber(line),
                line_end=LineNumber(end_line),
                column_start=ColumnNumber(column),
                column_end=ColumnNumber(column if end_column is None else end_column),
                is_primary=True,
            ),
        ),
        fixes=(),
    )
