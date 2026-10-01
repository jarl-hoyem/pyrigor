# JavaScript Object Notation diagnostics

`pyrigor --output-format=json path/` emits one JSON document to stdout. The default human-readable output is unchanged.
The normative v1 schema is [`schemas/pyrigor-diagnostics-v1.json`](../schemas/pyrigor-diagnostics-v1.json).

The top-level document contains `schema_version`, `diagnostics`, `errors`, and `summary`. The `diagnostics` contains
only unsuppressed rule violations. Read and parse failures are operational errors, not rule violations and appear in
`errors`. The same failures are also written as warnings to stderr.

Diagnostic `file` values use the path string pyrigor checked. Locations use 1-based Unicode code-point columns and
end-exclusive ranges. The JSON serializer converts Python AST's UTF-8 byte offsets to this representation. The `context`
is always present because it is part of pyrigor's diagnostic contract.

`fixability` is the rule's existing guideline classification. It does not mean that an edit is included in the response.
Automatic fixes and fix edits are out of scope for v1.

Diagnostics, suppressed diagnostics and errors are emitted in a fixed, deterministic order, independent of the
underlying filesystem's directory-enumeration order and of the order paths were given on the command line. Files are
ordered by their path string, compared with forward slashes by Unicode code point, so the same order holds regardless of
platform. Diagnostics and suppressed diagnostics are then ordered by line, column, end line, end column, then the rule's
code as a string, so two findings at the same position still order deterministically, independent of which checker
produced them. Errors are ordered by file. The human-readable output follows the same order for its finding lines, the
per-file summary and the skipped-file warnings written to stderr.

The summary counts all candidate files passed to the checker, kept diagnostics, and suppressed diagnostics. The
`suppressed_by_rule` is keyed by full rule code.

Consumers must select behaviour by `schema_version` and may ignore unknown future fields. Removing a required field,
changing a field's type or changing an enum value requires a new schema version. The v1 schema is otherwise closed so
producers can detect accidental field drift.
