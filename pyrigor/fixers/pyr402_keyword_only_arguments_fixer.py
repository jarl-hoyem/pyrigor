"""Opt-in fixer for PYR402 keyword-only arguments."""
# The fixer mirrors test cases to preserve exact source behaviour.
# pylint: disable=duplicate-code

import ast
import re
from enum import Enum
from typing import Final, NamedTuple

from pyrigor.checkers import WalkedNodes, is_type_guard_function, walk_once
from pyrigor.checkers.pyr402_keyword_only_arguments import find_findings as find_pyr402_findings
from pyrigor.finding_builder import FindingContext
from pyrigor.findings import FileName, PositionIndex, make_span
from pyrigor.suppression import filter_suppressed

_MINIMUM_POSITIONAL_PARAMETERS: Final = 2
_FIXER_FILE_NAME: Final = FileName("<fixer>.py")
_COMMA: Final = ","
_COMMA_OR_COMMENT: Final = re.compile(r"#[^\r\n]*|,")

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
    """Insert bare stars into eligible signatures with kept PYR402 findings."""
    original = source
    text = source.decode() if isinstance(source, bytes) else source
    normalised = text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    tree = ast.parse(normalised)
    raw = text.encode()
    index = PositionIndex(raw=raw)
    nodes = walk_once(tree=tree)
    context = FindingContext(source=normalised, index=index, file_name=_FIXER_FILE_NAME, parents=nodes.parents)
    target_positions = _kept_positions(context=context, nodes=nodes)
    edits = _source_edits(
        text=text,
        raw=raw,
        nodes=nodes.function_nodes,
        target_positions=target_positions,
        index=index,
    )

    if not edits:
        return FixResult(source=original, status=FixStatus.UNCHANGED)
    if dry_run:
        return FixResult(source=original, status=FixStatus.WOULD_CHANGE)

    return FixResult(
        source=_apply_edits(text=text, edits=edits, as_bytes=isinstance(source, bytes)), status=FixStatus.CHANGED
    )


def _kept_positions(*, context: FindingContext, nodes: WalkedNodes) -> set[int]:
    """Locate kept function signatures without tokenising clean files."""
    findings = find_pyr402_findings(nodes=nodes, context=context)
    kept = filter_suppressed(findings=findings, tokens=context.tokens if findings else None).kept
    # Original byte offsets match AST nodes without mixing human code-point columns with AST byte columns.
    return {next(span.byte_start for span in finding.spans if span.is_primary) for finding in kept}


def _apply_edits(*, text: str, edits: list[_Insertion], as_bytes: bool) -> str | bytes:
    """Apply source edits from right to left and preserve the input type."""
    for position, insertion in reversed(edits):
        text = "".join((text[:position], insertion, text[position:]))
    return text.encode() if as_bytes else text


def _source_edits(
    *,
    text: str,
    raw: bytes,
    nodes: list[ast.FunctionDef | ast.AsyncFunctionDef],
    target_positions: set[int],
    index: PositionIndex,
) -> list[_Insertion]:
    """Collect eligible edits for functions with kept PYR402 findings."""
    edits: list[_Insertion] = []
    for node in nodes:
        if index.byte_offset(line=node.lineno, utf8_column=node.col_offset) not in target_positions:
            continue
        edit = _function_edit(text=text, raw=raw, node=node, index=index)
        if edit is not None:
            edits.append(edit)
    return edits


def _function_edit(
    *, text: str, raw: bytes, node: ast.FunctionDef | ast.AsyncFunctionDef, index: PositionIndex
) -> _Insertion | None:
    """Return a safe insertion for one function if it needs fixing.

    A TypeGuard or TypeIs function gets its star after the guarded parameter, because a leading
    bare star would make that parameter keyword-only.
    """
    if node.args.posonlyargs:
        raise FixRejectedError(f"positional-only parameters in {node.name}")
    positional = node.args.args
    if len(positional) < _MINIMUM_POSITIONAL_PARAMETERS or node.args.vararg is not None:
        return None
    if is_type_guard_function(node=node):
        return _guard_insertion(text=text, raw=raw, node=node, index=index)
    return _function_insertion(text=text, raw=raw, node=node, positional=positional, index=index)


def _guard_insertion(
    *, text: str, raw: bytes, node: ast.FunctionDef | ast.AsyncFunctionDef, index: PositionIndex
) -> _Insertion:
    """Return the insertion after the comma that ends the guarded parameter.

    The guarded parameter is the first one after an optional leading self/cls. Its end comes from
    the syntax tree and covers any annotation and default, so the comma search never
    sees commas inside either.
    """
    guarded = 1 if node.args.args[0].arg in {"self", "cls"} else 0
    end_node = _guarded_end_node(node=node, guarded=guarded)
    byte_end = make_span(node=end_node, index=index, file_name=_FIXER_FILE_NAME).byte_end
    return _Insertion(_comma_after(text=text, start=len(raw[:byte_end].decode())) + 1, " *,")


def _guarded_end_node(*, node: ast.FunctionDef | ast.AsyncFunctionDef, guarded: int) -> ast.arg | ast.expr:
    """Return the node whose end closes the guarded parameter: its default if it has one, else itself."""
    positional = node.args.args
    default_index = guarded - (len(positional) - len(node.args.defaults))
    return node.args.defaults[default_index] if default_index >= 0 else positional[guarded]


def _comma_after(*, text: str, start: int) -> int:
    """Find the first comma at or after a position, skipping comments.

    Only closing parentheses, whitespace, line continuations and comments can sit between the end of
    a parameter and its separating comma, so the search never meets a comma inside a string or bracket.
    """
    return next(match.start() for match in _COMMA_OR_COMMENT.finditer(text, start) if match.group() == _COMMA)


def _function_insertion(
    *,
    text: str,
    raw: bytes,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    positional: list[ast.arg],
    index: PositionIndex,
) -> _Insertion:
    """Return a source insertion for an eligible function.

    The search below has no end bound. `node.lineno`/`col_offset` always lands on the `def`
    (or `async`) keyword itself, past any decorator. The function's own name is therefore the
    only text between `start` and its opening parenthesis. The first "(" found from `start` is
    therefore always this function's own, regardless of what a later function in the file
    contains.
    """
    start_byte = index.byte_offset(line=node.lineno, utf8_column=node.col_offset)
    start = len(raw[:start_byte].decode())
    opening = text.find("(", start)
    if opening == -1:
        raise FixRejectedError(f"unsupported signature in {node.name}")
    return _parameter_insertion(text=text, node=node, positional=positional, opening=opening)


def _parameter_insertion(
    *, text: str, node: ast.FunctionDef | ast.AsyncFunctionDef, positional: list[ast.arg], opening: int
) -> _Insertion:
    """Return the insertion point and text for a safe signature edit.

    The comma search below has no end bound either. It only runs for a self/cls method.
    `_function_edit`'s own `_MINIMUM_POSITIONAL_PARAMETERS` guard already requires at least one
    parameter after self/cls, so a real separating comma always exists before this function's
    own body. That comma is always the first one to be found from `opening`.
    """
    if positional[0].arg not in {"self", "cls"}:
        separator = "*," if text.startswith(("\n", "\r"), opening + 1) else "*, "
        return _Insertion(opening + 1, separator)
    comma = text.find(",", opening)
    if comma == -1:
        raise FixRejectedError(f"unsupported signature in {node.name}")
    return _Insertion(comma + 1, " *,")
