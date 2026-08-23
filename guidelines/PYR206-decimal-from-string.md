# PYR206 — Construct Decimal from a string literal, never a float literal

## Rule

Construct `Decimal` values from a string literal, never a float
literal.

```python
# Bad
price = Decimal(1.1)

# Good
price = Decimal("1.1")
```

## Rationale

`Decimal(1.1)` does not construct the value `1.1`. It constructs the
exact binary floating-point representation of `1.1`, which is not
`1.1` at all:
`Decimal('1.100000000000000088817841970012523233890533447265625')`.
`Decimal("1.1")` gives the exact, intended decimal value. This
silently defeats the entire reason `Decimal` was reached for, usually money
or another value where exact decimal precision genuinely matters. The tools
mypy and ruff both pass this cleanly. It is fully type-correct and
syntactically fine.

## Fix classification

**Kind:** `safe_fix`

**Reasoning:** Replacing `Decimal(1.1)` with `Decimal("1.1")` is
mechanically safe and directly corrects the actual, virtually always
intended behavior, an exact decimal value. No design judgment is
required.

## Severity

**Level:** `error`

**Reasoning:** Constructs a different value than the one
written — a real precision bug. See `DECISIONS.md`'s "Severity"
entry for the full per-rule reasoning.

## When this does not apply

- A `Decimal` constructed from an existing `int`, another `Decimal`,
  or a variable already holding one of these, not a float literal.
- A deliberate, explicitly commented case where the exact binary
  float representation genuinely is the intended value.

## Related

None yet.

## Enforced by

Not yet implemented.
