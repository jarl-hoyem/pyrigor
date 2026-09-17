# Finding model

## Purpose

Findings in pyrigor use a structured diagnostic model designed for machine consumers, editors and human-readable
renderers.

The model adopts established diagnostic vocabulary from Ruff and rustc where that vocabulary fits pyrigor. The finding
is semantic data. Rendering is a separate concern.

The types, their fields and the position conventions are defined once, in
[`schemas/pyrigor-diagnostics-v2.json`](../schemas/pyrigor-diagnostics-v2.json). This document gives the reasons.

## Why this model

The existing `Violation` type is intentionally small, but it mixes the concepts of a finding, its source location and
the information needed by future consumers. That makes incremental extension a poor design strategy: adding fields one
at a time would preserve assumptions from the old representation rather than defining a coherent diagnostic contract.

The target model therefore starts from the needs of a modern diagnostic consumer and then chooses established
terminology wherever possible.

### Reuse established vocabulary

Ruff and rustc already expose diagnostics to editors, automation and humans. Reusing their canonical names reduces
translation between pyrigor and the surrounding Python tooling ecosystem and makes the model easier for consumers to
understand.

This is why pyrigor uses names such as `code`, `message`, `spans`, `is_primary`, `label` and `applicability` rather than
inventing pyrigor-specific synonyms.

The goal is not to copy either format wholesale. Their models contain concepts specific to their implementations.
Instead, pyrigor adopts vocabulary and structure where it has a clear fit and deliberately rejects concepts that do not.

### Structured spans instead of one location

A finding is not necessarily about one source position. Some diagnostics naturally involve several locations: a
declaration and its use, two values that should not be confused or a source location plus the place where a consequence
occurs.

A `spans` collection therefore provides a durable model for both simple and multi-location findings. The `is_primary`
field identifies the focal location without imposing a single-span representation.

Exactly one span is primary, so every consumer that shows a single location shows the same one. A secondary span may be
in another file because a related definition does not always live next to the finding.

### Keep exact byte ranges

Line and column information is necessary for human diagnostics, but exact byte offsets provide a stronger machine-level
source range. They are useful for editor integration and precise edits. They also save every consumer from
reconstructing offsets from line and column information.

Byte offsets count the raw bytes of the file, not the decoded text. Reading a file as text removes a byte-order mark and
can translate line endings, so offsets into decoded text would not match the file an editor or a fixer writes back.

### Columns count characters

Columns count Unicode code points. The tools rustc and Ruff, whose field names the model uses, count characters too, so
a consumer that trusts the names reads the right unit. Byte positions already live in `byte_start` and `byte_end`, so
counting bytes in the columns as well would repeat them in a unit no reader counts in.

### Lines break where Python's parser breaks them

A line ends at a line feed, a CRLF or a lone carriage return, the same places Python's parser ends a line. Other
characters that `str.splitlines()` treats as breaks, such as U+2028 or a form feed, are not line breaks here. Treating
them as breaks would put a finding on a different line than the one Python reports.

A line's break characters belong to the line they end. Every byte offset then has exactly one line and column, including
the positions at the end of a line and at the end of a file.

### Separate semantic data from rendering

A finding should describe what was found, where it was found and what action may be proposed. It should not contain a
pre-rendered presentation of that information.

Different consumers may need terminal output, JSON, editor diagnostics, HTML or another representation. Keeping
rendering outside the semantic model avoids coupling the finding contract to one presentation format.

For the same reason, `rendered` is deliberately excluded.

### Do not duplicate source text

The source text is already available to consumers from the referenced source file and range. Copying source excerpts
into every finding creates duplicated data that can become stale and increases the size of the semantic model.

Therefore, `text` is deliberately excluded from the core model. A particular output format may enrich diagnostics with
source excerpts when appropriate.

### Record where a finding is

A baseline or a trend report needs to recognise the same finding after unrelated lines have changed. Positions alone
cannot do that, because every position moves when a line above it changes.

A finding therefore records its enclosing symbol: the innermost function, method or class that contains it, or the
module. Its name follows Python's own `__qualname__`, such as `Class.method` or `outer.<locals>.inner`. That form is
already defined by Python, and it keeps two nested functions with the same name apart. How a baseline turns the symbol
into a fingerprint is left to the baseline itself.

Python normalises an identifier to Normalisation Form KC, so a function written with fullwidth letters defines the plain
name. A symbol name is stored in that form, so one symbol has one spelling, for the same reason a file name is stored in
NFC.

Because the name is a `__qualname__`, its shape follows from its kind. Every segment is a Python identifier, a method's
name ends with its class, and a function is either at module level or directly inside another function. A name that
contradicts its kind cannot come from Python, so the schema rejects it rather than letting a consumer build identity on
it.

### One spelling per file

Sorting findings and matching them against a baseline both compare file names as strings. The same file must therefore
always be written the same way: relative, with forward slashes, without `.` segments, without whitespace at the edges of
a segment and in Unicode normalisation form NFC. Any other spelling of a path pyrigor reports would make one file look
like two.

### Text cannot disguise itself

File names, symbol names, messages and labels are shown to people, in terminals, editors and reports. Zero-width
characters, bidirectional controls and invisible fillers can make such a text display differently from what it contains,
which is how "Trojan Source" attacks hide code. The schema rejects them in all shown text and requires every message and
label to contain a visible character. Edit content is the exception, because a fix can need such a character inside a
string literal it writes.

Control characters are rejected in shown text too, including tabs and line breaks. A terminal escape sequence in a
message can recolour or overwrite output, and a line break can forge a line that looks like another finding.

### Fixes are structured actions

A fix is more than replacement text. Consumers need to know what kind of change is proposed, why it is proposed and
which source ranges it changes.

Therefore, a fix has an `applicability`, a `message` and one or more `edits`. Each edit identifies a byte range and
replacement content.

A finding carries a list of fixes, not a single one. Some findings can be resolved in more than one way, and a list lets
those alternatives exist without a breaking change. A consumer applies at most one of them.

An edit has its own shape rather than reusing a span. The `is_primary` and `label` mean nothing on an edit, and
repeating lines and columns there would give an edit two sets of coordinates that could disagree exactly where
correctness matters most. The edits of one fix refer to the original file, are sorted and do not overlap, so applying
them needs no knowledge of the order in which they were produced. They are also all in the same file because applying
edits to several files together is a separate problem no fixer has.

The `applicability` field deliberately uses Ruff's terminology (`safe`, `unsafe`, `display`). The meaning of each value
is recorded with the fix classification decision.

### Keep rule metadata separate from the finding

A rule definition describes the rule itself: its identity, default severity, fixability, rationale and documentation. A
finding describes one concrete occurrence in one source location.

Keeping those concerns separate avoids duplicating the rule-definition structure inside every finding. A rule's
documentation link is a property of the rule, the same for every finding, so it belongs with the rule metadata rather
than in each finding.

The finding carries `code`, `message` and `level` directly, so each finding stays readable on its own.

### Absent values have one representation

A list is always present, even when empty, and only `fixes` may be empty. An optional value is omitted when absent,
never written as `null`. Consumers then never handle a missing list, and never handle both a missing field and a `null`
one.

### Grow without breaking consumers

Planned features will add information to findings, such as suppression state and baseline state. The schema therefore
states an extension policy: consumers ignore fields they do not know, and adding an optional field is a compatible
change. The tool pyrigor still validates its own output strictly, so a field it did not intend to emit is caught.

### Validation stays linear

A consumer validates whatever it receives, including hostile documents. The `uniqueItems` keyword compares every item
with every other, so a single finding with a few thousand spans took seconds to validate. The schema therefore does not
use it, and uniqueness of spans, fixes and edits is an invariant the producer guarantees.

### What the schema leaves to the producer

Some rules cannot be expressed in JSON Schema: an offset not after its end, sorted and non-overlapping edits, offsets
within the file, NFC and valid Unicode, a code that names a rule pyrigor defines and a level that matches the severity
pyrigor assigns to that rule. The schema lists them as invariants for the producer, and tests pin that the schema
accepts each violation, so a later change that starts enforcing one updates the list deliberately.

The Python types in `pyrigor/findings.py` enforce the invariants a validator cannot: an ordered byte range, an ordered
position, sorted and non-overlapping edits in one file, unique spans and fixes, valid Unicode, a file name in NFC, a
qualified name whose segments are identifiers and a level derived from the rule. Positions come from `PositionIndex`, so
a span's offsets lie within the file, on code-point boundaries and never inside a byte-order mark or a CRLF.

They do not repeat the rules the schema states, such as the text patterns, the path spelling or the shape a name must
have for its kind. Those hold because pyrigor validates its own output against the schema. A type therefore accepts
values the schema rejects, and the document, not the object, is where that is caught.

### No document validates before the wrapper exists

The schema defines finding types, but not yet the document that carries them. Until the document wrapper is defined, the
schema's root rejects every document, so nothing can pass validation against a contract that is incomplete.

### Do not import implementation-specific machinery

Some Ruff and rustc fields exist because of their particular implementations rather than because diagnostics universally
need them.

The `expansion` field is useful for Rust macro expansion but has no concrete pyrigor equivalent today. The `noqa_row`
field is Ruff-specific suppression metadata rather than part of the semantic finding. Neither belongs in the canonical
model.

Suppression remains a separate concern. A later version of pyrigor may expose suppression locations to editors, but that
does not make suppression location part of the finding itself.

### Add structure when a rule needs it

The compiler rustc attaches child diagnostics to a finding, and notebook diagnostics carry a cell. No current or planned
pyrigor rule needs either. The uses of children are covered by secondary spans with labels and by the list of fixes, and
Ruff's own JSON diagnostics have no children. A notebook cell also left undefined whether lines and bytes count from the
cell or from the file.

Both are therefore left out. Under the extension policy, either can be added later as an optional field when a rule or a
consumer needs it.

## Canonical model

The schema defines these types:

- `Finding`
- `Span`
- `EnclosingSymbol`
- `Fix`
- `Edit`

It also defines `FileName`, `ByteOffset` and `LinePosition` once, and spans and edits refer to them, so the two cannot
disagree.

Their fields, the position conventions, the worked position examples and the invariants the schema cannot express are in
[`schemas/pyrigor-diagnostics-v2.json`](../schemas/pyrigor-diagnostics-v2.json).

## Vocabulary decisions

Where Ruff and rustc provide established terminology, pyrigor reuses it rather than inventing project-specific synonyms.

In particular:

- `code` identifies the rule.
- `message` describes the finding.
- `level` describes diagnostic severity or purpose.
- `spans` represent source locations.
- `is_primary` identifies the principal location.
- `label` explains the significance of a span.
- `applicability` describes the status of a proposed fix.

## Deliberately excluded fields

The following rustc/Ruff fields are not part of the canonical finding model:

- `rendered`: rendering is a consumer concern.
- `text`: source text is available from the referenced source.
- `expansion`: no current pyrigor equivalent justifies it.
- `noqa_row`: suppression metadata is separate from the semantic finding.
- `children`: no rule needs child diagnostics yet.
- `cell`: no notebook support exists, and its line and byte base was undefined.
- `url`: a documentation link belongs to the rule, not to each finding.

## Future capabilities

A later version of pyrigor may expose suppression locations to editors so that tools can navigate to, create or modify
suppressions. Suppression location is therefore a future diagnostic capability, not part of the core finding.

Child diagnostics and notebook cells can be added as optional fields under the extension policy when they are needed.

## Separation from migration

This document defines only the target model for findings.

It does not prescribe how the existing `Violation` model is migrated, whether compatibility is maintained or how
existing consumers are changed.

Migration is a separate implementation decision and should reference this document as its target specification.
