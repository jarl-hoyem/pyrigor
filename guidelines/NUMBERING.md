# Rule numbering scheme

Every `PYRxxx` rule code is a three-digit number. The first digit is
a topical bucket. This document is the convention for choosing that
number, alongside [`NAMING.md`](./NAMING.md), which covers the
symbolic name slug rather than the number itself.

## Buckets

| Range | Topic                                       |
|-------|---------------------------------------------|
| 1xx   | Imports                                     |
| 2xx   | Values (types, constants, closed states)    |
| 3xx   | Data structures (containers, records)       |
| 4xx   | Functions (signatures, returns, parameters) |
| 5xx   | Control flow                                |

## Deciding a bucket

Ask what the rule is actually protecting, not where the problem
happens to surface first. A rule can surface inside a function
signature and still belong to a different bucket if the underlying
concern is about a value, or a data structure rather than the
function itself.

Example: [PYR201](./PYR201-newtype-same-typed-values.md) (`NewType`
for same-typed values) is 2xx, not 4xx, even though the motivating
example was a function argument swap. The rule protects any
same-typed value at risk of confusion, everywhere, not
specifically function arguments. Contrast with
[PYR402](./PYR402-keyword-only-arguments.md), which is genuinely
about function call sites specifically and correctly sits in 4xx.

## Reserved but unwritten rules

A rule number can be reserved in [`BACKLOG.md`](./BACKLOG.md) before
its guideline doc exists, by noting "planned as PYR xxx" against the
relevant backlog item. This prevents a later rule from
claiming the same number, which has happened once already in this
project’s history (a file was misnamed `PYR404` when it should have
been `PYR405`, colliding with the already-reserved mutable-defaults
number).

## Current allocations

As of this writing:

- **1xx**: none yet.
- **2xx**: PYR201 (`NewType`), PYR202 (`Enum`), PYR203 (`Final`).
- **3xx**: PYR301 (`NamedTuple` for values).
- **4xx**: PYR401 (`NamedTuple` returns), PYR402/PYR403
  (keyword-only arguments), PYR404 (reserved, mutable defaults, not
  yet written), PYR405 (`NamedTuple` parameters), PYR406 (return
  values used).
- **5xx**: none yet.

Check [`BACKLOG.md`](./BACKLOG.md) and the existing `guidelines/`
directory for the current highest number in a bucket before claiming
the next one, rather than relying on this table alone, since it can
go stale.

## Adding a new rule

See [`ADDING_A_RULE.md`](./ADDING_A_RULE.md) for the full checklist,
including where numbering fits into the overall process.
