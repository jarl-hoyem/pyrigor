# Finding Model

## Purpose

PyRigor findings use a structured diagnostic model designed for machine consumers, editors, and human-readable
renderers.

The model adopts established diagnostic vocabulary from Ruff and rustc where that vocabulary fits PyRigor. The finding
is semantic data; rendering is a separate concern.

## Why this model

The existing `Violation` type is intentionally small, but it mixes the concepts of a finding, its source location, and
the information needed by future consumers. That makes incremental extension a poor design strategy: adding fields one
at a time would preserve assumptions from the old representation rather than defining a coherent diagnostic contract.

The target model therefore starts from the needs of a modern diagnostic consumer and then chooses established
terminology wherever possible.

### Reuse established vocabulary

Ruff and rustc already expose diagnostics to editors, automation, and humans. Reusing their canonical names reduces
translation between PyRigor and the surrounding Python tooling ecosystem and makes the model easier for consumers to
understand.

This is why PyRigor uses names such as `code`, `message`, `spans`, `is_primary`, `label`, and `applicability` rather
than inventing PyRigor-specific synonyms.

The goal is not to copy either format wholesale. Their models contain concepts specific to their implementations.
PyRigor adopts vocabulary and structure where it has a clear fit and deliberately rejects concepts that do not.

### Structured spans instead of one location

A finding is not necessarily about one source position. Some diagnostics naturally relate several locations: a
declaration and its use, two values that should not be confused, or a source location plus the place where a consequence
occurs.

A `spans` collection therefore provides a durable model for both simple and multi-location findings. `is_primary`
identifies the focal location without imposing a single-span representation.

This also gives editors and other consumers precise source ranges without requiring them to reconstruct the diagnostic
from a checker-specific context model.

### Keep exact byte ranges

Line and column information is necessary for human diagnostics, but exact byte offsets provide a stronger machine-level
source range. They are useful for editor integration and precise edits, and avoid making every consumer reconstruct
offsets from line/column information.

Therefore `byte_start` and `byte_end` are part of the target model even though the current AST-based implementation
naturally works with line and column positions.

### Separate semantic data from rendering

A finding should describe what was found, where it was found, and what action may be proposed. It should not contain a
pre-rendered presentation of that information.

Different consumers may need terminal output, JSON, editor diagnostics, HTML, or another representation. Keeping
rendering outside the semantic model avoids coupling the finding contract to one presentation format.

For the same reason, `rendered` is deliberately excluded.

### Do not duplicate source text

The source text is already available to consumers from the referenced source file and range. Copying source excerpts
into every finding creates duplicated data that can become stale and increases the size of the semantic model.

Therefore `text` is deliberately excluded from the core model. A particular output format may enrich diagnostics with
source excerpts when appropriate.

### Children are explanatory diagnostics

Some diagnostics need more than one explanation. A main finding can have related child diagnostics that point to
supporting locations or explain why the main diagnostic exists.

The `children` structure provides this relationship without forcing unrelated information into the main message or span.
Rust's current diagnostic model demonstrates this pattern.

PyRigor deliberately does not make children recursively nested at this stage. The current use case needs attached
explanatory diagnostics, not an arbitrarily deep diagnostic tree.

### Fixes are structured actions

A fix is more than replacement text. Consumers need to know what kind of change is proposed, why it is proposed, and
which source ranges it changes.

Therefore a fix has an `applicability`, a `message`, and one or more `edits`. Each edit identifies a span and
replacement content.

`applicability` deliberately uses Ruff's terminology and practical three-level semantics (`safe`, `unsafe`, `display`).
This is more useful for PyRigor than copying rustc's four internal applicability values because PyRigor's fix model is
aimed at the same practical distinction: what may be applied automatically, what requires explicit opt-in, and what
should only be presented as a suggestion.

### Keep rule metadata separate from the finding

A rule definition describes the rule itself: its identity, default severity, fixability, rationale, and documentation. A
finding describes one concrete occurrence in one source location.

Keeping those concerns separate allows the diagnostic to be self-contained for consumers while avoiding duplication of
rule-definition structure inside every finding.

The finding therefore carries `code`, `message`, and `level` directly rather than requiring consumers to reconstruct the
diagnostic from `RuleInfo`.

### Do not import implementation-specific machinery

Some Ruff and rustc fields exist because of their particular implementations rather than because diagnostics universally
need them.

`expansion` is useful for Rust macro expansion but has no concrete PyRigor equivalent today. `noqa_row` is Ruff-specific
suppression metadata rather than part of the semantic finding. Neither belongs in the canonical model.

Suppression remains a separate concern. PyRigor may later expose suppression locations to editors, but that does not
make suppression location part of the finding itself.

### Preserve notebook compatibility without committing to notebook support

A `cell` field is retained as an optional span property because notebook diagnostics can identify a cell in addition to
a file. Keeping the field costs little and avoids unnecessarily constraining the model.

Its presence does not commit PyRigor to implementing notebook analysis. It simply keeps the target diagnostic model
compatible with that potential consumer context.

## Canonical model

A finding consists of:

- `code`
- `message`
- `level`
- `spans`
- `children`
- `fix` (optional)
- `url` (optional)

### Span

Each span consists of:

- `file_name`
- `cell` (optional)
- `byte_start`
- `byte_end`
- `line_start`
- `line_end`
- `column_start`
- `column_end`
- `is_primary`
- `label`

Multiple spans are supported. `is_primary` identifies the focal span.

### Child diagnostic

A child diagnostic consists of:

- `code`
- `message`
- `level`
- `spans`

Children are explanatory diagnostics attached to the main finding. Child diagnostics are not recursively nested.

### Fix

A fix consists of:

- `applicability`
- `message`
- `edits`

Each edit identifies a `span` and replacement `content`.

## Vocabulary decisions

Where Ruff and rustc provide established terminology, PyRigor reuses it rather than inventing project-specific synonyms.

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

- `rendered` — rendering is a consumer concern.
- `text` — source text is available from the referenced source.
- `expansion` — no current PyRigor equivalent justifies it.
- `noqa_row` — suppression metadata is separate from the semantic finding.

`byte_start` and `byte_end` are retained because exact source ranges are useful for editor integration and precise
fixes.

## Future capabilities

PyRigor may expose suppression locations to editors so that tools can navigate to, create, or modify suppressions.
Suppression location is therefore a future diagnostic capability, not part of the core finding.

Notebook support is compatible with this model. Retaining the optional `cell` field does not commit PyRigor to
implementing notebook analysis.

## Separation from migration

This document defines the target finding model only.

It does not prescribe how the existing `Violation` model is migrated, whether compatibility is maintained, or how
existing consumers are changed.

Migration is a separate implementation decision and should reference this document as its target specification.
