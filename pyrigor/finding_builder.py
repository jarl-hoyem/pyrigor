"""Build canonical findings from checker nodes and their shared source context."""

import ast
import io
import tokenize
from bisect import bisect_left
from dataclasses import dataclass, field
from typing import Final, Literal, NamedTuple, TypeAlias

from pyrigor.findings import EnclosingSymbol, FileName, Finding, PositionIndex, SymbolKind, make_span
from pyrigor.rules import Rule

_SIGNATURE_COLON: Final = ":"
_FUNCTION_TYPES: Final = (ast.FunctionDef, ast.AsyncFunctionDef)
_SCOPE_TYPES: Final = (*_FUNCTION_TYPES, ast.ClassDef)
_LOCALS_SEGMENT: Final = "<locals>"
_MODULE_NAME: Final = "<module>"

_FunctionNode: TypeAlias = ast.FunctionDef | ast.AsyncFunctionDef
_ScopeNode: TypeAlias = _FunctionNode | ast.ClassDef
_FindingNode: TypeAlias = _FunctionNode | ast.AnnAssign | ast.Call


class _TokenPosition(NamedTuple):
    """A token's '1-based' line and '0-based' code-point column."""

    line: int
    column: int


class _TokenData(NamedTuple):
    """The file's tokens and their ordered positions, shared by all function findings."""

    tokens: tuple[tokenize.TokenInfo, ...]
    starts: tuple[tuple[int, int], ...]


class _Subject(NamedTuple):
    """The legacy message's context kind and source subject."""

    kind: Literal["Function", "Variable", "Call"]
    name: str


@dataclass(slots=True, kw_only=True)
class FindingContext:
    """The source and positions shared by every checker for one file.

    The source has decoded UTF-8 and universal newlines. The index retains the original raw bytes, including a BOM
    and the original line breaks. Parent relationships come from the pipeline's single shared AST walk.
    """

    source: str
    index: PositionIndex
    file_name: FileName
    parents: dict[ast.AST, ast.AST]
    _token_data: _TokenData | None = field(default=None, init=False, repr=False)
    _headers: dict[_FunctionNode, ast.Expr] = field(
        default_factory=dict[_FunctionNode, ast.Expr], init=False, repr=False
    )

    def _tokens(self) -> _TokenData:
        """Tokenise once for signature ranges and suppression comments."""
        if self._token_data is None:
            tokens = tuple(tokenize.generate_tokens(io.StringIO(self.source).readline))
            self._token_data = _TokenData(
                tokens=tokens,
                starts=tuple(token.start for token in tokens),
            )
        return self._token_data

    @property
    def tokens(self) -> tuple[tokenize.TokenInfo, ...]:
        """The shared token stream, created only when a finding needs it."""
        return self._tokens().tokens

    def header_node(self, *, node: _FunctionNode) -> ast.Expr:
        """Return the cached source range from the function keyword through its signature colon.

        Args:
            node: The function whose signature is the finding's focal range.

        Returns:
            A positioned expression node for the canonical span constructor.
        """
        if node not in self._headers:
            self._headers[node] = _header_node(node=node, index=self.index, token_data=self._tokens())
        return self._headers[node]


def _token_position(*, node: ast.stmt | ast.expr, index: PositionIndex) -> _TokenPosition:
    """Convert an AST's byte-based column into a token's code-point column."""
    offset = index.byte_offset(line=node.lineno, utf8_column=node.col_offset)
    position = index.position(offset=offset)
    return _TokenPosition(line=position.line, column=position.column - 1)


def _body_position(*, node: _FunctionNode, index: PositionIndex) -> _TokenPosition:
    """Locate the first body statement, including its decorators when it is another definition."""
    first = node.body[0]
    position = _token_position(node=first, index=index)
    # A nested definition's decorators belong to the body and can contain colons of their own.
    if isinstance(first, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and first.decorator_list:
        position = min(_token_position(node=decorator, index=index) for decorator in first.decorator_list)
    return position


def _header_node(*, node: _FunctionNode, index: PositionIndex, token_data: _TokenData) -> ast.Expr:
    """Find the final signature colon before the body and preserve the AST's original byte-based start."""
    if node.end_lineno is None or node.end_col_offset is None:
        raise ValueError("node has no end position")
    token = _signature_colon(node=node, index=index, token_data=token_data)
    return ast.Expr(
        value=ast.Constant(value=None),
        lineno=node.lineno,
        col_offset=node.col_offset,
        end_lineno=token.end[0],
        end_col_offset=len(token.line[: token.end[1]].encode()),
    )


def _signature_colon(*, node: _FunctionNode, index: PositionIndex, token_data: _TokenData) -> tokenize.TokenInfo:
    """Find the final colon token between the definition keyword and its first body statement."""
    start_position = _token_position(node=node, index=index)
    body_position = _body_position(node=node, index=index)
    start = bisect_left(token_data.starts, (start_position.line, start_position.column))
    end = bisect_left(token_data.starts, (body_position.line, body_position.column))
    # Annotations and defaults can contain earlier colons; the last one before the body ends the signature.
    for token in reversed(token_data.tokens[start:end]):
        if token.type == tokenize.OP and token.string == _SIGNATURE_COLON:
            return token
    raise ValueError("function signature has no colon in its source context")


def _source_name(*, node: ast.expr, source: str) -> str:
    """Keep plain legacy names and describe other targets with their original source text."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return _source_subject(node=node, source=source)


def _source_subject(*, node: ast.expr, source: str) -> str:
    """Describe an expression with its source, making non-printable characters visible."""
    name = ast.get_source_segment(source, node)
    if name is None:
        raise ValueError("finding subject has no source range")
    return "".join(character if character.isprintable() else repr(character)[1:-1] for character in name)


def _subject(*, node: _FindingNode, source: str) -> _Subject:
    """Identify a function, assignment target or callee for the rule's message."""
    if isinstance(node, ast.AnnAssign):
        return _Subject(kind="Variable", name=_source_name(node=node.target, source=source))
    if isinstance(node, ast.Call):
        return _Subject(kind="Call", name=_source_name(node=node.func, source=source))
    return _Subject(kind="Function", name=node.name)


def _scope_chain(*, node: ast.AST, parents: dict[ast.AST, ast.AST]) -> list[_ScopeNode]:
    """Collect the innermost definition and each definition enclosing it."""
    scopes: list[_ScopeNode] = [node] if isinstance(node, _SCOPE_TYPES) else []
    parent = parents.get(node)
    if parent is not None:
        scopes.extend(_scope_chain(node=parent, parents=parents))
    return scopes


def _qualified_name(*, scopes: list[_ScopeNode]) -> str:
    """Build Python's qualified name, inserting <locals> below each enclosing function."""
    segments = [scopes[0].name]
    for ancestor in scopes[1:]:
        segment = ancestor.name
        if isinstance(ancestor, _FUNCTION_TYPES):
            segment = f"{segment}.{_LOCALS_SEGMENT}"
        segments.insert(0, segment)
    return ".".join(segments)


def _symbol_kind(*, scopes: list[_ScopeNode]) -> SymbolKind:
    """Distinguish a class, a function and a function defined in a class scope."""
    if isinstance(scopes[0], ast.ClassDef):
        return SymbolKind.CLASS
    if len(scopes) > 1 and isinstance(scopes[1], ast.ClassDef):
        return SymbolKind.METHOD
    return SymbolKind.FUNCTION


def _enclosing_symbol(*, node: ast.AST, parents: dict[ast.AST, ast.AST]) -> EnclosingSymbol:
    """Record the innermost named definition or the module when none encloses the finding."""
    scopes = _scope_chain(node=node, parents=parents)
    if not scopes:
        return EnclosingSymbol(kind=SymbolKind.MODULE, name=_MODULE_NAME)
    return EnclosingSymbol(kind=_symbol_kind(scopes=scopes), name=_qualified_name(scopes=scopes))


def _span_node(*, node: _FindingNode, context: FindingContext) -> ast.stmt | ast.expr:
    """Choose a function signature or the complete affected statement as the primary range."""
    if isinstance(node, _FUNCTION_TYPES):
        return context.header_node(node=node)
    parent = context.parents.get(node)
    if isinstance(node, ast.Call) and isinstance(parent, ast.Expr):
        return parent
    return node


def make_finding(*, node: _FindingNode, rule: Rule, context: FindingContext) -> Finding:
    """Build a canonical finding from a checker's node and the shared source context.

    Args:
        node: The function, annotated assignment or call statement flagged by the checker.
        rule: The rule whose problem text and severity describe the finding.
        context: The file's source, raw-byte positions and shared AST parents.

    Returns:
        One finding with a primary span, an enclosing symbol and no proposed fixes.

    Raises:
        ValueError: If the node lacks a complete source range, or its signature is absent from the context.
    """
    span = make_span(node=_span_node(node=node, context=context), index=context.index, file_name=context.file_name)
    subject = _subject(node=node, source=context.source)
    return Finding(
        code=rule,
        message=f"{subject.kind} '{subject.name}' {rule.problem}",
        spans=(span,),
        enclosing_symbol=_enclosing_symbol(node=node, parents=context.parents),
        fixes=(),
    )
