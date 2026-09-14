# Finding Model

## Purpose

PyRigor findings use a structured diagnostic model designed for machine consumers, editors, and human-readable renderers.

The model adopts established diagnostic vocabulary from Ruff and rustc where that vocabulary fits PyRigor. The finding is semantic data; rendering is a separate concern.

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

`applicability` follows the Ruff terminology and distinguishes changes that can safely be applied automatically from changes requiring greater caution or manual presentation.

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

`byte_start` and `byte_end` are retained because exact source ranges are useful for editor integration and precise fixes.

## Future capabilities

PyRigor may expose suppression locations to editors so that tools can navigate to, create, or modify suppressions. Suppression location is therefore a future diagnostic capability, not part of the core finding.

Notebook support is compatible with this model. Retaining the optional `cell` field does not commit PyRigor to implementing notebook analysis.

## Separation from migration

This document defines the target finding model only.

It does not prescribe how the existing `Violation` model is migrated, whether compatibility is maintained, or how existing consumers are changed.

Migration is a separate implementation decision and should reference this document as its target specification.
