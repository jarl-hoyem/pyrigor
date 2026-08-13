# PYR203 — Use `Final` named constants instead of magic numbers

## Rule

A bare numeric literal carrying a specific, reused meaning must
be replaced with a named `Final` constant.

```python
# Bad
if retries > 3:
    raise MaxRetriesExceeded

# Good
from typing import Final

MAX_RETRIES: Final = 3

if retries > MAX_RETRIES:
    raise MaxRetriesExceeded
```

## Rationale

A magic number is a literal value with no name attached to explain
what it represents or why that specific value was chosen. Read in
isolation, `if retries > 3:` gives no indication of what `3` means,
whether it is a deliberate limit or an arbitrary leftover, or whether
every other place in the codebase that should respect the same limit
actually uses the same number.

```python
if retries > 3:
    ...

# Elsewhere, meant to be the same limit, but nothing enforces it:
if attempt_count >= 3:
    ...

# A later change updates one and not the other. Both still run.
# Neither raises an error. The two limits have silently diverged.
```

A named `Final` constant fixes both problems at once. The name
documents intent at the point of use, and every reference to the
same constant is guaranteed to share the same value, because there
is only one place the value is ever written.

```python
MAX_RETRIES: Final = 3

if retries > MAX_RETRIES:
    ...

if attempt_count >= MAX_RETRIES:
    ...

# Change MAX_RETRIES once. Every reference updates. There is no
# second copy of the number to forget.
```

`Final` also gives mypy a real check to run: if anything later tries
to rebind the constant (`MAX_RETRIES = 5` somewhere else), mypy flags
it as an error, rather than silently allowing a "constant" to
stop being constant.

This is the same underlying failure shape as
[PYR202](./PYR202-enum-not-magic-strings.md) — the unnamed literal
standing in for a value that should be a documented, singular source
of truth. It is applied to numeric values with a specific significance,
rather than to values from a closed set of named states. Use
[PYR202](./PYR202-enum-not-magic-strings.md) when the numbers
represent a fixed set of named alternatives (`Enum`). Use PYR203 when
the number is a single, specific threshold, limit, or coefficient
with no sibling values to enumerate against.

## When this does not apply

- Genuinely self-explanatory numbers with no reuse risk and no
  meaningful name to give them — `0` and `1` used as plain arithmetic
  identities (`x + 0`, indexes, loop bounds like `range(len(items))`),
  not as configuration or business-rule values.
- A single, local, one-off value used exactly once, where a named
  constant would add a layer of indirection without adding clarity
  (a test asserting an arbitrary but fixed input value, for example).
- Numbers whose meaning is already fully carried by their immediate
  context and unlikely to ever be reused or need to change in
  lockstep elsewhere.

## Related

- [PYR202](./PYR202-enum-not-magic-strings.md) — the same underlying
  problem for a closed set of named states, addressed with `Enum`
  rather than `Final`.

- [PYR205](./PYR205-final-constants.md) — the structurally
  detectable subset of this rule: a numeric literal duplicated
  across a file, independently adoptable, not a stricter or looser
  mode of the same rule.

## Enforced by

Not yet implemented.
