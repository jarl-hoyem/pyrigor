"""Version two diagnostics documents and their operational errors."""

from collections.abc import Sequence
from itertools import dropwhile
from typing import Final, Literal, NamedTuple

from pyrigor.findings import (
    REJECTED_DIAGNOSTIC_TEXT,
    FileName,
    Finding,
    JsonObject,
    escape_diagnostic_text,
    finding_to_json,
    require_file_name,
)
from pyrigor.rules import Applicability, FixAvailability, Rule

_PARENT_SEGMENT: Final = ".."
ErrorKind = Literal["read_error", "parse_error", "malformed_suppression"]


class DiagnosticInputError(ValueError):
    """Input that the current diagnostics producer cannot represent faithfully."""


def require_representable_file_name(*, file_name: FileName, path: str) -> None:
    """Stop before any file is read when the schema would reject a file's name.

    Args:
        file_name: The relative, NFC-normalised name built from the path.
        path: The path as given or found, named in the message.

    Raises:
        DiagnosticInputError: Naming the path and the rule and suggesting --exclude.
    """
    problem = _file_name_problem(file_name=file_name)
    if problem is not None:
        raise DiagnosticInputError(f"{path!r}: {problem}; use --exclude to skip this file")


def _file_name_problem(*, file_name: FileName) -> str | None:
    """Name the first rule of the schema's FileName that the name breaks, or None when it keeps them all."""
    unsupported = REJECTED_DIAGNOSTIC_TEXT.search(file_name)
    if unsupported is not None:
        code_point = f"U+{ord(unsupported.group()):04X}"
        return f"the file name contains {code_point}, which the current v2 producer cannot represent"
    try:
        require_file_name(file_name=file_name)
    except ValueError as error:
        return str(error)
    segments = file_name.split("/")
    return _segment_problem(segments=segments) or _whitespace_problem(segments=segments)


def _segment_problem(*, segments: Sequence[str]) -> str | None:
    """Apply the schema's segment rules, which the relative-path check leaves to the schema."""
    ordinary = list(dropwhile(lambda segment: segment == _PARENT_SEGMENT, segments))
    if {"", "."} & set(segments) or not ordinary or _PARENT_SEGMENT in ordinary:
        return "file_name has an empty, current-directory or misplaced parent-directory segment"
    return None


def _whitespace_problem(*, segments: Sequence[str]) -> str | None:
    """Apply the schema's rule that no segment starts or ends with whitespace."""
    if any(segment != segment.strip() for segment in segments):
        return "file_name has a segment that starts or ends with whitespace"
    return None


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
    result: JsonObject = {
        "file_name": error.file_name,
        "kind": error.kind,
        "message": escape_diagnostic_text(text=error.message),
    }
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
    """Serialise the wrapper using the canonical finding serialiser."""
    return {
        "schema_version": 2,
        "tool": document.tool._asdict(),
        "findings": [finding_to_json(finding=finding) for finding in document.findings],
        "suppressed": [finding_to_json(finding=finding) for finding in document.suppressed],
        "rules": {rule.name: _rule_to_json(metadata=metadata) for rule, metadata in document.rules.items()},
        "errors": [error_to_json(error=error) for error in document.errors],
        "summary": {"files_checked": document.summary.files_checked},
    }
