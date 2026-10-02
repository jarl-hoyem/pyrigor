"""Version two diagnostics documents and their operational errors."""

import re
from typing import Final, Literal, NamedTuple

from pyrigor.findings import FileName, Finding, JsonObject, finding_to_json
from pyrigor.rules import Applicability, FixAvailability, Rule

ErrorKind = Literal["read_error", "parse_error", "malformed_suppression"]
_UNSUPPORTED_IDENTIFIER_TEXT: Final = re.compile("[\u034f\u115f\u1160\u200c\u200d]")


class DiagnosticInputError(ValueError):
    """Input that the current diagnostics producer cannot represent faithfully."""


def require_supported_findings(*, findings: list[Finding], path: str) -> None:
    """Fail explicitly until #344 implements visible escapes for rejected identifier characters."""
    for finding in findings:
        _require_supported_text(text=finding.message, path=path)
        if finding.enclosing_symbol is not None:
            _require_supported_text(text=finding.enclosing_symbol.name, path=path)


def _require_supported_text(*, text: str, path: str) -> None:
    """Reject the known valid identifier characters forbidden literally by the v2 text rules."""
    unsupported = _UNSUPPORTED_IDENTIFIER_TEXT.search(text)
    if unsupported is not None:
        code_point = f"U+{ord(unsupported.group()):04X}"
        raise DiagnosticInputError(
            f"{path!r}: diagnostic text contains {code_point}, which the current v2 producer cannot represent"
        )


class CheckError(NamedTuple):
    """A source problem reported separately from rule findings."""

    file_name: FileName
    kind: ErrorKind
    message: str
    line: int | None = None
    column: int | None = None


class ToolMetadata(NamedTuple):
    """The producing tool and installed release."""

    name: Literal["pyrigor"]
    version: str


class RuleMetadata(NamedTuple):
    """Selected rule metadata shared by kept and suppressed findings."""

    symbolic_name: str
    fix_availability: FixAvailability
    applicability: Applicability | None
    url: str


class Summary(NamedTuple):
    """The number of distinct files attempted, including unsuccessful reads."""

    files_checked: int


class DiagnosticsDocument(NamedTuple):
    """The complete public version two output wrapper."""

    tool: ToolMetadata
    findings: list[Finding]
    suppressed: list[Finding]
    rules: dict[Rule, RuleMetadata]
    errors: list[CheckError]
    summary: Summary


def error_to_json(*, error: CheckError) -> JsonObject:
    """Omit unavailable positions rather than serialising nulls."""
    result: JsonObject = {"file_name": error.file_name, "kind": error.kind, "message": error.message}
    if error.line is not None:
        result["line"] = error.line
    if error.column is not None:
        result["column"] = error.column
    return result


def _rule_to_json(*, metadata: RuleMetadata) -> JsonObject:
    """Serialise rule applicability only when the rule has fixes."""
    result: JsonObject = {
        "symbolic_name": metadata.symbolic_name,
        "fix_availability": metadata.fix_availability.value,
        "url": metadata.url,
    }
    if metadata.applicability is not None:
        result["applicability"] = metadata.applicability.value
    return result


def document_to_json(*, document: DiagnosticsDocument) -> JsonObject:
    """Serialise the wrapper using the canonical finding serializer."""
    return {
        "schema_version": 2,
        "tool": document.tool._asdict(),
        "findings": [finding_to_json(finding=finding) for finding in document.findings],
        "suppressed": [finding_to_json(finding=finding) for finding in document.suppressed],
        "rules": {rule.name: _rule_to_json(metadata=metadata) for rule, metadata in document.rules.items()},
        "errors": [error_to_json(error=error) for error in document.errors],
        "summary": {"files_checked": document.summary.files_checked},
    }
