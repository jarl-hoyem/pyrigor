"""Exercise canonical finding production across source layouts, scopes and raw-byte positions."""

import ast
import tokenize
from typing import NamedTuple, TypeVar
from unittest.mock import patch

import pytest

from pyrigor.finding_builder import FindingContext, make_finding
from pyrigor.findings import FileName, Finding, PositionIndex, SymbolKind, finding_to_json
from pyrigor.rules import Rule
from tests.diagnostics_v2_support import Json, definition_validator

_NodeT = TypeVar("_NodeT", bound=ast.AST)
_FILE_NAME = FileName("src/example.py")
_UTF8_BOM = b"\xef\xbb\xbf"


class _Parsed(NamedTuple):
    """The parsed source and the original bytes against which findings are checked."""

    tree: ast.Module
    context: FindingContext
    raw: bytes


def _parse(*, source: str | bytes) -> _Parsed:
    """Parse the same universal-newline text and retain the original UTF-8 bytes."""
    raw = source.encode() if isinstance(source, str) else source
    text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    tree = ast.parse(text)
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    context = FindingContext(source=text, index=PositionIndex(raw=raw), file_name=_FILE_NAME, parents=parents)
    return _Parsed(tree=tree, context=context, raw=raw)


def _node(*, tree: ast.Module, node_type: type[_NodeT], index: int = 0) -> _NodeT:
    """Select a checker node of the requested kind from the shared tree."""
    return [node for node in ast.walk(tree) if isinstance(node, node_type)][index]


def _function(*, tree: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """Select a named synchronous or asynchronous function."""
    return next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )


def _text(*, parsed: _Parsed, finding: Finding) -> str:
    """Recover the exact raw-byte slice covered by the finding's primary span."""
    span = finding.spans[0]
    assert (
        len(finding.spans),
        span.is_primary,
        span.file_name,
        span.label is None,
        finding.fixes,
    ) == (
        1,
        True,
        _FILE_NAME,
        True,
        (),
    )
    return parsed.raw[span.byte_start : span.byte_end].decode()


# noinspection LongLine
@pytest.mark.parametrize(
    ("source", "signature"),
    [
        ("def flagged(item):\n    return item\n", "def flagged(item):"),
        ("async def flagged(item):\n    return item\n", "async def flagged(item):"),
        ("def flagged(item): return {'body': item}\n", "def flagged(item):"),
        ("def flagged(a,b):x:dict[str,int]={}\n", "def flagged(a,b):"),
        ("@decorate({'key': 1})\ndef flagged(item):\n    pass\n", "def flagged(item):"),
        ("def flagged(item='a:b'):\n    pass\n", "def flagged(item='a:b'):"),
        ("def flagged(item=lambda value: value):\n    pass\n", "def flagged(item=lambda value: value):"),
        (
            "def flagged(item: dict[str, int] = {'a': 1}) -> dict[str, int]:\n    pass\n",
            "def flagged(item: dict[str, int] = {'a': 1}) -> dict[str, int]:",
        ),
        ("def flagged() -> lambda: {'a': 1}: pass\n", "def flagged() -> lambda: {'a': 1}:"),
        (
            "def flagged(\n    item: str = 'colon:',\n    other=lambda: {'a': 1},\n) -> tuple[int, int]:\n    pass\n",
            "def flagged(\n    item: str = 'colon:',\n    other=lambda: {'a': 1},\n) -> tuple[int, int]:",
        ),
        (
            "def flagged(item='''first:\nsecond:'''):\n    pass\n",
            "def flagged(item='''first:\nsecond:'''):",
        ),
        (
            "def flagged(item):\n    @decorate({'key': 1})\n    def inner():\n        pass\n",
            "def flagged(item):",
        ),
        (
            "def flagged(item):\n    @decorate({'key': 1})\n    class Inner:\n        pass\n",
            "def flagged(item):",
        ),
        ("if ready:\n    def flagged(item):\n        pass\n", "def flagged(item):"),
    ],
)
def test_function_span_covers_only_the_complete_signature(*, source: str, signature: str) -> None:
    """Decorators, body colons and colons inside header expressions never alter the signature range."""
    parsed = _parse(source=source)
    node = _function(tree=parsed.tree, name="flagged")
    finding = make_finding(node=node, rule=Rule.PYR402, context=parsed.context)
    assert _text(parsed=parsed, finding=finding) == signature
    assert finding.message == f"Function 'flagged' {Rule.PYR402.problem}"
    assert finding.code is Rule.PYR402
    assert finding.level is Rule.PYR402.severity


def test_function_tokens_and_headers_are_shared_by_rules_and_nodes() -> None:
    """Several rules and functions reuse one tokenisation and the same cached header node."""
    parsed = _parse(source="def first(item): pass\ndef second(item): pass\n")
    first = _function(tree=parsed.tree, name="first")
    second = _function(tree=parsed.tree, name="second")
    with patch("pyrigor.finding_builder.tokenize.generate_tokens", wraps=tokenize.generate_tokens) as tokenise:
        first_finding = make_finding(node=first, rule=Rule.PYR402, context=parsed.context)
        repeated_finding = make_finding(node=first, rule=Rule.PYR403, context=parsed.context)
        second_finding = make_finding(node=second, rule=Rule.PYR405, context=parsed.context)
        assert parsed.context.header_node(node=first) is parsed.context.header_node(node=first)
    assert tokenise.call_count == 1
    assert first_finding.spans == repeated_finding.spans
    expected_signature = "def second(item):"
    assert _text(parsed=parsed, finding=second_finding) == expected_signature


@pytest.mark.parametrize(
    ("source", "statement", "subject"),
    [
        ("value: tuple[int, int] = (1, 2)\n", "value: tuple[int, int] = (1, 2)", "value"),
        ("self.value: tuple[int, int] = (1, 2)\n", "self.value: tuple[int, int] = (1, 2)", "value"),
        ("data[0]: tuple[int, int] = (1, 2)\n", "data[0]: tuple[int, int] = (1, 2)", "data[0]"),
        ("data[0]: tuple[int, int]; other = 1\n", "data[0]: tuple[int, int]", "data[0]"),
        (
            "if ready:\n    data[0]: tuple[int, int] = (\n        1, 2\n    ) # trailing comment\n",
            "data[0]: tuple[int, int] = (\n        1, 2\n    )",
            "data[0]",
        ),
    ],
)
def test_assignment_span_and_subject_describe_the_whole_statement(*, source: str, statement: str, subject: str) -> None:
    """Assignment findings include values and preserve useful source text for non-name targets."""
    parsed = _parse(source=source)
    finding = make_finding(
        node=_node(tree=parsed.tree, node_type=ast.AnnAssign), rule=Rule.PYR301, context=parsed.context
    )
    assert _text(parsed=parsed, finding=finding) == statement
    assert finding.message == f"Variable '{subject}' {Rule.PYR301.problem}"


@pytest.mark.parametrize(
    ("source", "statement", "subject"),
    [
        ("factory()\n", "factory()", "factory"),
        ("service.factory()\n", "service.factory()", "factory"),
        ("factories[0]()\n", "factories[0]()", "factories[0]"),
        ("factory()()\n", "factory()()", "factory()"),
        ("((factory()))\n", "((factory()))", "factory"),
        ("(\n    factory()\n)\n", "(\n    factory()\n)", "factory"),
        ("if ready: factory(); other()\n", "factory()", "factory"),
        ("factory() # trailing comment\n", "factory()", "factory"),
        ("(lambda: 1)()\n", "(lambda: 1)()", "lambda: 1"),
    ],
)
def test_call_span_includes_the_parent_statement_and_wrapping_parentheses(
    *, source: str, statement: str, subject: str
) -> None:
    """Discarded calls retain the statement's range and their legacy or source-derived subject."""
    parsed = _parse(source=source)
    finding = make_finding(node=_node(tree=parsed.tree, node_type=ast.Call), rule=Rule.PYR406, context=parsed.context)
    assert _text(parsed=parsed, finding=finding) == statement
    assert finding.message == f"Call '{subject}' {Rule.PYR406.problem}"


def test_call_without_an_expression_statement_parent_uses_its_own_range() -> None:
    """The constructor remains well-defined for calls passed directly from other expression contexts."""
    parsed = _parse(source="result = factory()\n")
    finding = make_finding(node=_node(tree=parsed.tree, node_type=ast.Call), rule=Rule.PYR406, context=parsed.context)
    expected_statement = "factory()"
    assert _text(parsed=parsed, finding=finding) == expected_statement


@pytest.mark.parametrize(
    ("target", "subject"),
    [
        ("data[\n    0\n]", "data[\\n    0\\n]"),
        ("data['\t']", "data['\\t']"),
        ("data['\u202e']", "data['\\u202e']"),
        ("data['\u00a0']", "data['\\xa0']"),
        ("data['\u2028']", "data['\\u2028']"),
        ("data['\U000e0001']", "data['\\U000e0001']"),
        ("data['\u00e9']", "data['\u00e9']"),
        ("data['\\n']", "data['\\n']"),
    ],
)
def test_non_plain_assignment_subject_escapes_only_invisible_source_characters(*, target: str, subject: str) -> None:
    """Multiline or invisible literal content remains visible in a single-line schema-valid message."""
    parsed = _parse(source=f"{target}: tuple[int, int]\n")
    finding = make_finding(
        node=_node(tree=parsed.tree, node_type=ast.AnnAssign), rule=Rule.PYR301, context=parsed.context
    )
    assert finding.message == f"Variable '{subject}' {Rule.PYR301.problem}"
    payload: Json = finding_to_json(finding=finding)
    definition_validator(definition="Finding").validate(payload)


def test_multiline_non_plain_callee_has_a_schema_valid_visible_subject() -> None:
    """A call producing the discarded call's callee retains a readable source without raw line breaks."""
    parsed = _parse(source="(factory(\n    argument\n))()\n")
    finding = make_finding(node=_node(tree=parsed.tree, node_type=ast.Call), rule=Rule.PYR406, context=parsed.context)
    subject = "factory(\\n    argument\\n)"
    assert finding.message == f"Call '{subject}' {Rule.PYR406.problem}"
    payload: Json = finding_to_json(finding=finding)
    definition_validator(definition="Finding").validate(payload)


@pytest.mark.parametrize(
    ("source", "name", "qualified_name", "kind"),
    [
        ("def flagged(item): pass\n", "flagged", "flagged", SymbolKind.FUNCTION),
        ("async def flagged(item): pass\n", "flagged", "flagged", SymbolKind.FUNCTION),
        ("class Store:\n    def flagged(self, item): pass\n", "flagged", "Store.flagged", SymbolKind.METHOD),
        (
            "class Store:\n    if ready:\n        async def flagged(self, item): pass\n",
            "flagged",
            "Store.flagged",
            SymbolKind.METHOD,
        ),
        (
            "def outer():\n    def flagged(item): pass\n",
            "flagged",
            "outer.<locals>.flagged",
            SymbolKind.FUNCTION,
        ),
        (
            "class Store:\n    def outer(self):\n        def flagged(item): pass\n",
            "flagged",
            "Store.outer.<locals>.flagged",
            SymbolKind.FUNCTION,
        ),
        (
            "def outer():\n    class Store:\n        def flagged(self, item): pass\n",
            "flagged",
            "outer.<locals>.Store.flagged",
            SymbolKind.METHOD,
        ),
        (
            "class Store:\n    class Inner:\n        def flagged(self, item): pass\n",
            "flagged",
            "Store.Inner.flagged",
            SymbolKind.METHOD,
        ),
        (
            "def outer():\n    def middle():\n        async def flagged(item): pass\n",
            "flagged",
            "outer.<locals>.middle.<locals>.flagged",
            SymbolKind.FUNCTION,
        ),
    ],
)
def test_function_symbol_is_the_flagged_definition_with_python_qualified_name(
    *, source: str, name: str, qualified_name: str, kind: SymbolKind
) -> None:
    """Definitions identify themselves and distinguish class methods from nested functions."""
    parsed = _parse(source=source)
    finding = make_finding(node=_function(tree=parsed.tree, name=name), rule=Rule.PYR402, context=parsed.context)
    assert finding.enclosing_symbol is not None
    assert finding.enclosing_symbol.name == qualified_name
    assert finding.enclosing_symbol.kind is kind


@pytest.mark.parametrize(
    ("source", "qualified_name", "kind"),
    [
        ("value: tuple[int, int]\n", "<module>", SymbolKind.MODULE),
        ("if ready:\n    value: tuple[int, int]\n", "<module>", SymbolKind.MODULE),
        ("class Store:\n    value: tuple[int, int]\n", "Store", SymbolKind.CLASS),
        ("class Store:\n    class Inner:\n        value: tuple[int, int]\n", "Store.Inner", SymbolKind.CLASS),
        ("def outer():\n    value: tuple[int, int]\n", "outer", SymbolKind.FUNCTION),
        (
            "class Store:\n    def method(self):\n        value: tuple[int, int]\n",
            "Store.method",
            SymbolKind.METHOD,
        ),
        (
            "def outer():\n    class Inner:\n        value: tuple[int, int]\n",
            "outer.<locals>.Inner",
            SymbolKind.CLASS,
        ),
    ],
)
def test_assignment_symbol_is_its_innermost_named_scope(*, source: str, qualified_name: str, kind: SymbolKind) -> None:
    """Statements identify their containing module, class, function or method."""
    parsed = _parse(source=source)
    finding = make_finding(
        node=_node(tree=parsed.tree, node_type=ast.AnnAssign), rule=Rule.PYR301, context=parsed.context
    )
    assert finding.enclosing_symbol is not None
    assert finding.enclosing_symbol.name == qualified_name
    assert finding.enclosing_symbol.kind is kind


def test_call_symbol_skips_intermediate_control_flow_nodes() -> None:
    """A call inside compound statements still identifies the containing named method."""
    parsed = _parse(source="class Store:\n    def method(self):\n        if ready:\n            factory()\n")
    finding = make_finding(node=_node(tree=parsed.tree, node_type=ast.Call), rule=Rule.PYR406, context=parsed.context)
    assert finding.enclosing_symbol is not None
    expected_name = "Store.method"
    assert finding.enclosing_symbol.name == expected_name
    assert finding.enclosing_symbol.kind is SymbolKind.METHOD


@pytest.mark.parametrize("raw_name", ["\u212a", "\uff2b", "\ufb03"])
def test_nfkc_names_retain_the_actual_source_range(*, raw_name: str) -> None:
    """AST-normalised identifiers, including expansions, never determine the source range's length."""
    parsed = _parse(source=f"def {raw_name}(item):\n    pass\n")
    node = _node(tree=parsed.tree, node_type=ast.FunctionDef)
    finding = make_finding(node=node, rule=Rule.PYR402, context=parsed.context)
    assert _text(parsed=parsed, finding=finding) == f"def {raw_name}(item):"
    assert finding.message == f"Function '{node.name}' {Rule.PYR402.problem}"
    assert finding.enclosing_symbol is not None
    assert finding.enclosing_symbol.name == node.name


@pytest.mark.parametrize("line_break", ["\n", "\r\n", "\r"])
@pytest.mark.parametrize("bom", [b"", _UTF8_BOM])
def test_raw_offsets_account_for_bom_line_breaks_and_non_ascii_text(*, line_break: str, bom: bytes) -> None:
    """Canonical byte offsets and code-point columns remain correct when the parsed source is normalised."""
    source = f"label = '\u00e9'{line_break}def flagged(item='\u20ac'):{line_break}    pass{line_break}"
    raw = bom + source.encode()
    parsed = _parse(source=raw)
    finding = make_finding(node=_function(tree=parsed.tree, name="flagged"), rule=Rule.PYR402, context=parsed.context)
    signature = "def flagged(item='\u20ac'):"
    assert _text(parsed=parsed, finding=finding) == signature
    span = finding.spans[0]
    assert (
        span.byte_start,
        span.byte_end,
        span.line_start == span.line_end == 2,
        span.column_start,
        span.column_end,
    ) == (
        raw.index(b"def flagged"),
        span.byte_start + len(signature.encode()),
        True,
        1,
        len(signature) + 1,
    )


def test_same_line_non_ascii_prefix_does_not_shift_statement_columns() -> None:
    """AST byte columns are converted to code-point columns after a non-ASCII statement prefix."""
    parsed = _parse(source="label = '\u00e9'; ((factory('\u20ac')))\n")
    finding = make_finding(node=_node(tree=parsed.tree, node_type=ast.Call), rule=Rule.PYR406, context=parsed.context)
    span = finding.spans[0]
    expected_statement = "((factory('\u20ac')))"
    assert _text(parsed=parsed, finding=finding) == expected_statement
    assert span.column_start == len("label = '\u00e9'; ") + 1
    assert span.column_end == len("label = '\u00e9'; ((factory('\u20ac')))") + 1


def test_multiline_statement_uses_original_crlf_byte_range() -> None:
    """A multiline statement includes original CRLF pairs rather than the parsed source's LF characters."""
    parsed = _parse(source=_UTF8_BOM + b"(\r\n    factory('\xc3\xa9')\r\n)\r\n")
    finding = make_finding(node=_node(tree=parsed.tree, node_type=ast.Call), rule=Rule.PYR406, context=parsed.context)
    expected_statement = "(\r\n    factory('\u00e9')\r\n)"
    statement_lines = expected_statement.split("\r\n")
    assert _text(parsed=parsed, finding=finding) == expected_statement
    span = finding.spans[0]
    assert (
        span.byte_start,
        span.line_start,
        span.line_end,
        span.column_start,
        span.column_end,
    ) == (
        len(_UTF8_BOM),
        1,
        len(statement_lines),
        1,
        len(statement_lines[-1]) + 1,
    )


def test_function_without_an_end_position_is_rejected() -> None:
    """Incomplete AST nodes fail with the canonical source-range error."""
    parsed = _parse(source="def flagged(item): pass\n")
    node = _function(tree=parsed.tree, name="flagged")
    node.end_lineno = None
    with pytest.raises(ValueError, match=r"^node has no end position$"):
        make_finding(node=node, rule=Rule.PYR402, context=parsed.context)


def test_function_with_a_mismatched_source_context_is_rejected() -> None:
    """A missing signature colon exposes an invalid context instead of producing a fabricated span."""
    parsed = _parse(source="def earlier(): pass\ndef flagged(item): pass\n")
    parsed.context.source = "def earlier(): pass\ndef flagged(item)  pass\n"
    with pytest.raises(ValueError, match=r"^function signature has no colon in its source context$"):
        make_finding(node=_function(tree=parsed.tree, name="flagged"), rule=Rule.PYR402, context=parsed.context)


def test_non_name_subject_without_its_source_range_is_rejected() -> None:
    """A malformed target never degrades to an unhelpful unknown subject."""
    parsed = _parse(source="data[0]: tuple[int, int]\n")
    node = _node(tree=parsed.tree, node_type=ast.AnnAssign)
    node.target.end_lineno = None
    with pytest.raises(ValueError, match=r"^finding subject has no source range$"):
        make_finding(node=node, rule=Rule.PYR301, context=parsed.context)
