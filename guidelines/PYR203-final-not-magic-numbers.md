# PYR203 — Use `Final` named constants for any number other than `0`, `1`, or `-1`

## Rule

Every numeric literal other than `0`, `1`, or `-1` must be replaced
with a named `Final` constant. This is a mechanical rule, not a
judgment call: no other number is exempt on the grounds of seeming
self-explanatory.

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
it as an error, rather than silently allowing a "constant" to stop
being constant.

Why draw the line at exactly `0`, `1`, and `-1`: all three are used
overwhelmingly as arithmetic or structural identities rather than
business-meaningful values. The numbers `0` and `1` as plain arithmetic identity
elements (`x + 0`, `x * 1`), or as the first index and count in a
sequence. Likewise `-1` carries its own, equally structural meaning in Python
specifically: indexing and slicing use it as the canonical way to
reference the last element (`items[-1]`) or reverse a sequence
(`items[::-1]`), a language-level convention, not a business decision.
In all three cases, naming the value would not add real information,
since its meaning is already fully carried by its syntactic role. Any
other number is far more likely to encode a real decision, a count, a
limit, a version, that deserves a name and carries a real risk of
silently diverging if left unnamed in more than one place.

This is the same underlying failure shape as
[PYR202](./PYR202-enum-not-magic-strings.md) — the unnamed literal
standing in for a value that should be a documented, singular source
of truth. It is applied to numeric values with a specific
significance, rather than to values from a closed set of named
states. Use [PYR202](./PYR202-enum-not-magic-strings.md) when the
numbers represent a fixed set of named alternatives (`Enum`). Use
PYR203 when the number is a single, specific threshold, limit, or
coefficient with no sibling values to enumerate against.

## Fix classification

**Kind:** `guidance`

**Reasoning:** Naming a magic number requires
understanding why that specific value was chosen, not just that it
appears in the code. The tool can flag the literal and point at this
guideline, but inventing a name like `MAX_RETRIES` versus something
else entirely is a real human judgment call, the same limiting
factor as PYR301/401/405's `NamedTuple` naming.

## Severity

**Level:** `info`

**Reasoning:** Readability/maintainability and drift prevention, not
a silent-wrong-output risk. See `DECISIONS.md`'s "Severity" entry
for the full per-rule reasoning.

## When this does not apply

- The literal is `0`, `1`, or `-1`. This is the only exemption.
- Genuinely ephemeral test or example code where the number is
  explicitly arbitrary, and the point of the code is unaffected by
  its exact value, still worth naming if reused more than once in
  the same file.

## Related

- [PYR202](./PYR202-enum-not-magic-strings.md) — the same underlying
  problem for a closed set of named states, addressed with `Enum`
  rather than `Final`.
- [PYR205](./PYR205-final-constants.md) — a narrower, independently
  adoptable rule catching only the subset of this problem where the
  same literal is duplicated across a file, a lighter starting point
  for a codebase not yet ready to adopt PYR203’s full scope.

## Enforced by

Not yet implemented.
