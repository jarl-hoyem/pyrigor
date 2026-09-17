# Rule numbering scheme

Every `PYRxxx` rule code is a three-digit number. The first digit is a topical bucket. This document is the convention
for choosing that number, alongside [`NAMING.md`](./NAMING.md), which covers the symbolic name slug rather than the
number itself.

## Buckets

| Range | Topic                                       |
| ----- | ------------------------------------------- |
| 1xx   | Imports                                     |
| 2xx   | Values (types, constants, closed states)    |
| 3xx   | Data structures (containers, records)       |
| 4xx   | Functions (signatures, returns, parameters) |
| 5xx   | Control flow                                |

## Deciding a bucket

Ask what the rule is actually protecting, not where the problem happens to surface first. A rule can surface inside a
function signature and still belong to a different bucket if the underlying concern is about a value, or a data
structure rather than the function itself.

Example: [PYR201](./PYR201-newtype-same-typed-values.md) (`NewType` for same-typed values) is 2xx, not 4xx, even though
the motivating example was a function argument swap. The rule protects any same-typed value at risk of confusion,
everywhere, not specifically function arguments. Contrast with [PYR402](./PYR402-keyword-only-arguments.md), which is
genuinely about function call sites specifically and correctly sits in 4xx.

## When a number is decided

A rule gets a number when its guideline document is created, not before. An issue about a candidate rule names the idea,
not a number. An issue is eventually closed, while the document endures, so a number claimed in an issue reserves
nothing and goes stale where nobody looks.

## Which numbers are taken?

The guideline documents are the allocation list. The files `guidelines/PYR*.md` say which numbers exist, and
`guidelines/RULES.md` is generated from them. Read that directory when choosing the next number in a bucket:

```bash
ls guidelines/PYR*.md
```

A number whose rule was rejected returns to the pool, so `PYR404` is free for reuse. See [`REJECTED.md`](./REJECTED.md).

## Adding a new rule

See [`ADDING_A_RULE.md`](./ADDING_A_RULE.md) for the full checklist, including where numbering fits into the overall
process.
