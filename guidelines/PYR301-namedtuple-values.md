# PYR301 — Use `NamedTuple` instead of a bare fixed-length `tuple` type

## Rule

Any value with a fixed-length `tuple` type annotation, where each
position has a distinct meaning, must use a `NamedTuple` instead —
whether it is a variable, a dataclass/attrs field, a dict value, or any
other typed value. Function parameters and return types are covered
by their own, more specific rules. See “Related” below.

This rule covers tuple-typed values outside function signatures.
Parameters and return annotations are governed by PYR405 and PYR401.

```python
# Bad
last_position: tuple[int, int] = (3, 7)

# Good
class Position(NamedTuple):
    row: int
    col: int

last_position: Position = Position(row=3, col=7)
```

## Rationale

A bare, fixed-length `tuple` type is positionally meaningful but
carries no names — `tuple[int, int]` says “two ints,” not “a row and
a column.” Every place that value is constructed, unpacked, or passed
around has to independently know and correctly apply the intended
ordering, with nothing but convention or a comment enforcing it.

```python
last_position: tuple[int, int] = (3, 7)

# Both of these type-check. Only one is correct, and nothing in the
# type says which.
row, col = last_position
col, row = last_position
```

This is the same failure shape
[PYR401](./PYR401-namedtuple-returns.md) addresses for function
returns and [PYR405](./PYR405-namedtuple-parameters.md)
addresses for function parameters — PYR301 is the general form,
covering every other place a bare positional tuple can appear: a
plain variable, a `dataclass` field, a value stored in a `dict`, an
item in a `list`. Wherever a fixed-length tuple’s positions carry
distinct meaning, the same ambiguity exists, regardless of whether a
function signature is involved at all.

`NamedTuple` closes it the same way throughout: named field access
removes the positional slot as an attack surface, both at
construction and at every point of use.

## Fix classification

**Kind:** `guidance`

**Reasoning:** Needs real, human naming judgment (the `NamedTuple`
class name, its field names), independent of any caller-safety
question. Per #105's own adopted classification.

## Severity

**Level:** `warning`

**Reasoning:** Real swap-risk protection, but partially caught by
other means and narrower blast radius than error-tier rules. See
`DECISIONS.md`'s "Severity" entry for the full per-rule reasoning.

## When this does not apply

- Genuinely homogeneous, order-independent, or unbounded-length tuples
  (`tuple[float, ...]`), where there is no fixed positional meaning to
  get wrong.
- Ephemeral local tuples created and unpacked in the same few lines,
  never stored or passed elsewhere.
- A tuple shape matching an external API, file format, or library
  convention this codebase must match exactly, where a `NamedTuple`
  wrapper would add unwrapping overhead at every boundary crossing.

## Related

- [PYR401](./PYR401-namedtuple-returns.md) — the same rule, scoped
  specifically to function return values.
- [PYR405](./PYR405-namedtuple-parameters.md) — the same
  rule, scoped specifically to function parameters.

## Enforced by

Not yet implemented.
