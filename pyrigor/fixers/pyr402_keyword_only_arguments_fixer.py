"""Opt-in fixer for PYR402 keyword-only arguments."""

import ast
from enum import Enum
from typing import NamedTuple

_MINIMUM_POSITIONAL_PARAMETERS = 2

__all__ = ["FixRejectedError", "FixResult", "FixStatus", "fix_source"]


class FixRejectedError(ValueError):
    """Raised when a PYR402 edit could change positional-call semantics."""


class FixStatus(Enum):
    """Describe whether a source fix was applied or is only prospective."""

    UNCHANGED = "unchanged"
    CHANGED = "changed"
    WOULD_CHANGE = "would_change"


class FixResult(NamedTuple):
    """Result of a PYR402 source fix attempt."""

    source: str | bytes
    status: FixStatus


class _Insertion(NamedTuple):
    """Describe one source insertion."""

    position: int
    text: str


def fix_source(*, source: str | bytes, dry_run: bool = False) -> FixResult:
    """Insert bare stars into safe fixable PYR402 function signatures."""
    original = source
    text = source.decode() if isinstance(source, bytes) else source
    tree = ast.parse(text)
    offsets = _line_offsets(text=text)
    edits = _source_edits(text=text, tree=tree, offsets=offsets)

    if not edits:
        return FixResult(source=original, status=FixStatus.UNCHANGED)
    if dry_run:
        return FixResult(source=original, status=FixStatus.WOULD_CHANGE)

    return FixResult(
        source=_apply_edits(text=text, edits=edits, as_bytes=isinstance(source, bytes)), status=FixStatus.CHANGED
    )


def _apply_edits(*, text: str, edits: list[_Insertion], as_bytes: bool) -> str | bytes:
    """Apply source edits from right to left and preserve the input type."""
    for position, insertion in reversed(edits):
        text = "".join((text[:position], insertion, text[position:]))
    return text.encode() if as_bytes else text


def _line_offsets(*, text: str) -> list[int]:
    """Return the absolute offset of each source line."""
    offsets: list[int] = []
    total = 0
    for line in text.splitlines(keepends=True):
        offsets.append(total)
        total += len(line)
    return offsets


def _source_edits(*, text: str, tree: ast.AST, offsets: list[int]) -> list[_Insertion]:
    """Collect safe edits for every function in a source tree."""
    edits: list[_Insertion] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            edit = _function_edit(text=text, node=node, offsets=offsets)
            if edit is not None:
                edits.append(edit)
    return edits


def _function_edit(*, text: str, node: ast.FunctionDef | ast.AsyncFunctionDef, offsets: list[int]) -> _Insertion | None:
    """Return a safe insertion for one function if it needs fixing."""
    if node.args.posonlyargs:
        raise FixRejectedError(f"positional-only parameters in {node.name}")
    positional = node.args.args
    if len(positional) < _MINIMUM_POSITIONAL_PARAMETERS or node.args.vararg is not None:
        return None
    return _function_insertion(text=text, node=node, positional=positional, offsets=offsets)


def _function_insertion(
    *, text: str, node: ast.FunctionDef | ast.AsyncFunctionDef, positional: list[ast.arg], offsets: list[int]
) -> _Insertion:
    """Return a source insertion for an eligible function."""
    start = offsets[node.lineno - 1] + node.col_offset
    end_line = node.end_lineno or node.lineno
    end_column = node.end_col_offset or 0
    end = offsets[end_line - 1] + end_column
    opening = text.find("(", start, end)
    if opening < 0:
        raise FixRejectedError(f"unsupported signature in {node.name}")
    return _parameter_insertion(text=text, node=node, positional=positional, opening=opening, end=end)


def _parameter_insertion(
    *, text: str, node: ast.FunctionDef | ast.AsyncFunctionDef, positional: list[ast.arg], opening: int, end: int
) -> _Insertion:
    """Return the insertion point and text for a safe signature edit."""
    if positional[0].arg not in {"self", "cls"}:
        return _Insertion(opening + 1, "*, ")
    comma = text.find(",", opening, end)
    if comma < 0:
        raise FixRejectedError(f"unsupported signature in {node.name}")
    return _Insertion(comma + 1, " *,")
