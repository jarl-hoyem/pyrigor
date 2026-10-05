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
always be written the same way: relative, with forward slashes, without `.` segments, with `..` segments only at the
start (a file outside the working directory is `../app.py`), without whitespace at the edges of a segment and in Unicode
normalisation form NFC. Any other spelling of a path pyrigor reports would make one file look like two.

### Text cannot disguise itself

File names, symbol names, messages and labels are shown to people, in terminals, editors and reports. Zero-width
characters, bidirectional controls and invisible fillers can make such a text display differently from what it contains,
which is how "Trojan Source" attacks hide code. The schema rejects them in all shown text and requires every message and
label to contain a visible character. Edit content is the exception, because a fix can need such a character inside a
string literal it writes.

Control characters are rejected in shown text too, including tabs and line breaks. A terminal escape sequence in a
message can recolour or overwrite output, and a line break can forge a line that looks like another finding.

A symbol name may contain an escape for a character this rule rejects: a backslash, `u` and four lowercase hexadecimal
digits, or a backslash, `U` and eight. Python accepts a few such characters in identifiers, so the escape is how a
symbol named with one is reported. A real identifier cannot contain a backslash, so the escape is unambiguous, and the
name stays a stable identity. The schema checks only the shape of an escape. That it stands for a rejected character,
and that its code point is at most U+10FFFF, are producer rules.

The hidden-character rules list code points up to U+FFFF only. A pattern cannot match a character above U+FFFF the same
way everywhere. ECMAScript reads it as two surrogate code units unless the `u` flag is set, and a schema cannot set that
flag. Python's `re` module has no `\p{...}` category match to use instead. The schema therefore accepts astral format
characters, such as the tag characters U+E0000 to U+E007F and the variation selectors U+E0100 to U+E01EF, in messages,
labels, file names and symbol names. Tests pin this limit, so a later change that enforces it does so deliberately.

### Patterns are portable across regex engines

JSON Schema's `pattern` keyword is ECMAScript regex by specification, but every validator runs it through its own
language's engine. The schema is a contract for consumers beyond pyrigor's own Python validator, including editors
written in JavaScript or TypeScript and future Rust tooling, so every pattern avoids constructs engines disagree on
rather than relying on Python's own `re` behaviour.

No pattern uses a lookahead or a backreference. Engines built on RE2, such as Rust's `regex` crate and Go's `regexp`,
have no lookaheads at all, so a validator using one would reject the schema outright. A rule that reads naturally as "no
forbidden character anywhere" is instead written with JSON Schema's own `not` combined with a plain, unanchored
`pattern`. That needs no lookahead and no anchor, since "does the forbidden pattern match anywhere" is exactly what
`not` plus a search already means.

No pattern anchors a character-class exclusion with a bare trailing `$`. In Python, `$` also matches just before a final
line feed, not only at the true end of the string. A character class built to exclude line breaks still lets one through
right at the end, because `$` accepts the position before it. The `not`/`pattern` form above has no such problem, since
it never anchors the end at all. It was reached only after a first attempt using `^[^...]*$` reintroduced exactly this
defect, caught by the existing hostile-input test for a trailing newline in a symbol name.

No pattern relies on `\s` or `\d`. Python's `\s` includes U+001C to U+001F. ECMAScript additionally includes U+FEFF,
which Python's does not. Both are replaced everywhere with an explicit character class of Unicode's actual `White_Space`
characters, deliberately excluding both engine-specific extras, since neither is genuine whitespace. The schema's
hidden-character rules already reject both characters outright wherever the whitespace class is checked alongside them.
A future field that checks whitespace without also rejecting hidden characters would need to revisit this.

Python's `\d` matches any Unicode decimal digit. ECMAScript's matches only ASCII `0` to `9`. The enclosing symbol's
identifier grammar therefore uses `[0-9]` where it used `\d`. This loosens one rule. A segment of a symbol name may now
start with a non-ASCII decimal digit, such as U+0660, which the old pattern rejected. A Python identifier never starts
with a decimal digit, so such a name cannot be real, and the producer's own type still rejects it. The schema already
checks non-ASCII characters loosely because a pattern cannot carry Unicode categories portably, so this is one more
character the schema leaves to the producer. A test pins that the schema accepts it.

Five patterns anchor a grammar of allowed characters with `$`: the symbolic name of a rule, the whitespace rule for a
file name segment, the two grammars of a symbol name and the grammar of a method name. Python's `$` also matches before
a final line feed and ECMAScript's does not. No anchored pattern closes that gap because one engine can skip a final
line feed that the other has to consume. Each of these patterns therefore ends in `\n*$`, so it accepts any run of final
line feeds in both engines and reads the same everywhere. Rejecting a line feed is left to the shared rule for control
characters and, for the symbolic name of a rule, to its own rule against whitespace. Both reject a line feed wherever it
stands. A pattern that has to reject a line feed itself needs a `not` rule with an unanchored search instead.

The check in `scripts/check_schema_pattern_portability.py` runs every pattern in Python and in Node against more than
twenty thousand strings, each also tried with a final line feed. Node runs twice, without flags and with the `u` flag
that ajv, the most common JavaScript validator, sets by default. The check fails the commit when Python and either run
of Node disagree, so a pattern that reintroduces the gap is caught before it reaches a consumer.

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

A rule definition describes the rule itself: its identity, default severity, fix availability, applicability, rationale
and documentation. A finding describes one concrete occurrence in one source location.

Keeping those concerns separate avoids duplicating the rule-definition structure inside every finding. A rule's
documentation link is a property of the rule, the same for every finding, so it belongs with the rule metadata rather
than in each finding.

The finding carries `code`, `message` and `level` directly, so each finding stays readable on its own.

### Absent values have one representation

Document lists are always present and may be empty. Within a finding, only `fixes` may be empty. An optional value is
omitted when absent, never written as `null`. Consumers then never handle a missing list or two forms of absence.

### Grow without breaking consumers

Planned features will add information to findings, such as suppression state and baseline state. The schema therefore
states an extension policy: consumers ignore fields they do not know, and adding an optional field is a compatible
change. The tool pyrigor still validates its own output strictly, so a field it did not intend to emit is caught.

The schema is the strict producer contract. A consumer seeking forward compatibility parses its known fields and ignores
unknown ones. It cannot validate a newer document against an older strict schema and expect added fields to pass.
Keeping one strict schema avoids maintaining a second consumer schema or a generation step.

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
position, sorted and non-overlapping edits in one file, unique spans and fixes, valid Unicode, a relative file name with
forward slashes in NFC, a non-blank label, a qualified name whose segments are identifiers and a level derived from the
rule. Positions come from `PositionIndex`, so spans and edits built through `make_span` and `make_edit` lie within the
file, on code-point boundaries and never inside a byte-order mark or a CRLF.

They do not repeat the rules the schema states, such as the text patterns or the shape a name must have for its kind.
Those hold because pyrigor validates its own output against the schema. A type therefore accepts values the schema
rejects, and the document, not the object, is where that is caught.

### One document describes one run

The schema root references `Document`. Its version lets every consumer identify the contract before interpreting the
results. The tool name and version let a baseline identify the producer independently of the schema version.

The `findings` list contains kept findings. Editors, CI and reports consume it. The separate `suppressed` list lets
editors display suppressed findings differently without treating them as live findings. List membership carries the
suppression state. A suppression reason can be added later as an optional field.

The `rules` object includes every selected rule, even a rule with no findings. A report can show what was checked and
resolve each finding's metadata through its code. Editors can use its fix availability and applicability when offering
actions. Applicability is omitted when fix availability is `none`, matching the absence convention. Severity is not
repeated here because each finding's `level` is its authority.

A rule's URL points to its guideline on GitHub at the producing version's release tag. The guideline documents are not
in the wheel. Pinning the link ensures a report describes the rule version that actually produced its findings.

Operational errors let CI distinguish a complete run from one that could not check every file. Editors receive the same
information without reading stderr. Parse errors and malformed suppression comments can carry line and column
coordinates. A read error has no source position.

The summary records files that are checked, including files with operational errors. Clean files have no list entries,
so this count cannot be recovered from the findings. Counts derivable from the lists are deliberately excluded.

The document has no timings or other run-dependent fields. A usage error or a crash emits no document. The CLI emits
this contract only after the separate migration in #269.

### Document invariants belong to the producer

The schema validates each finding and rule entry separately. The producer must also ensure that every kept or suppressed
finding has a matching rule entry and that the rule's object contains exactly the selected rules. Metadata must agree
with the rule, including a documentation URL pinned to the producing tool version.

The producer orders findings and suppressed findings by the primary span's file name and full start and end position,
then code. It orders operational errors by file name and then line where present, and rules by code. These conventions
are stated in the schema's `x-invariants`. JSON Schema cannot enforce their cross-references or ordering. Tests pin that
such violations validate, so #269 must enforce them explicitly.

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

- `Document`
- `Tool`
- `Rules` and `RuleMetadata`
- `OperationalError`
- `Summary`
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
