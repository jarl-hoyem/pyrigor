# JavaScript Object Notation diagnostics

`pyrigor --output-format=json path/` emits one v2 JSON document to stdout. The normative schema is
[`schemas/pyrigor-diagnostics-v2.json`](../schemas/pyrigor-diagnostics-v2.json).

The document contains `schema_version`, `tool`, `findings`, `suppressed`, `rules`, `errors` and `summary`. The schema
version is `2`. The tool identity contains pyrigor's name and installed version. Kept findings appear in `findings`;
suppressed findings appear separately in `suppressed` with the same shape. Read, parse and malformed-suppression
failures are operational errors. Human output also reports warnings to stderr. The summary contains only
`files_checked`, including files with operational errors. List lengths provide finding counts.

Each finding has a rule `code`, subject-bearing `message`, severity `level`, `spans`, `enclosing_symbol` and `fixes`.
Exactly one span is primary. Function primary spans start at `def` or `async def` and end after the signature colon.
Assignment and call primary spans cover their statements. Suppression checks the line directly above the primary span
and every line within it. A comment elsewhere in a function body cannot suppress a signature finding.

Span `file_name` values are NFC-normalised paths relative to the working directory, using forward slashes.
Parent-directory segments are allowed for files outside that directory. Raw `byte_start` and `byte_end` include the
original UTF-8 BOM and line-ending bytes. Lines and columns are 1-based; columns count Unicode code points. Ranges are
end-exclusive. Python line breaks are LF, CRLF and lone CR; U+2028 and form feed do not start new lines. The CLI reads
bytes once, then decodes UTF-8-sig with universal newlines for parsing and tokenising. Human output uses the same
code-point columns. Signature spans and suppression reuse one token stream per file.

The enclosing symbol is the innermost function, method or class, using Python's NFKC-normalised qualified name.
Module-level findings use `{"kind": "module", "name": "<module>"}`. Subjects belong in messages, rather than symbols.
Every emitted finding currently has `fixes: []`. Rule metadata describes fix availability separately, including unsafe
applicability. The existing explicit PYR402 `--fix` and `--diff` workflows remain available.

The `rules` object contains exactly the selected rules, including rules with no findings. Each entry gives the symbolic
name, fix availability, applicability where relevant and guideline URL. URLs are pinned to the installed tool version's
release tag.

Findings and suppressed findings are ordered by their primary span's file name, start line, start column, end line, end
column and then rule code. Errors are ordered by file name and line where present; rules are ordered by code. Output
contains no timing or other run-dependent values. Usage errors and crashes emit no diagnostics document.

Consumers must select behaviour by `schema_version` and ignore unknown fields. Producers validate strictly against the
schema. Adding an optional field is compatible; removing a field or changing its type or meaning requires a new version.
