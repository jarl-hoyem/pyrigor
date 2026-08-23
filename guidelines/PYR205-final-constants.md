# PYR205 — Use a `Final` constant for a numeric literal repeated across a file

## Rule

A numeric literal that appears, identically, more than once in the
same file must be replaced with a single named `Final` constant,
referenced everywhere it was previously duplicated.

```python
# Bad
if retries > 3:
    raise MaxRetriesExceeded

while attempt_count < 3:
    attempt_count += 1

# Good
from typing import Final

MAX_RETRIES: Final = 3

if retries > MAX_RETRIES:
    raise MaxRetriesExceeded

while attempt_count < MAX_RETRIES:
    attempt_count += 1
```

## Rationale

This is a narrower, structurally checkable sibling of
[PYR203](./PYR203-final-not-magic-numbers.md), not a replacement for it.
PYR203’s full scope, any numeric literal whose meaning is not
self-evident, cannot be reliably detected from syntax alone. Whether
a given `3` is meaningful, or an incidental loop bound is a judgment
call an AST cannot make. PYR205 sidesteps that judgment entirely by
checking a different, purely structural question: does this exact
number appear more than once in this file, with no name attached to
either occurrence.

Duplication is not incidental to the underlying bug this family of
rules exists to prevent, it is the exact mechanism by which the bug
happens. A single, one-off numeric literal used exactly once cannot
diverge from itself. The failure mode
[PYR203](./PYR203-final-not-magic-numbers.md)'s own rationale
describes, two places meant to enforce the same limit silently
drifting apart after only one of them is updated, requires the
number to already be duplicated before it can diverge.

```python
if retries > 3:
    ...

# Elsewhere in the same file, meant to be the same limit:
if attempt_count >= 3:
    ...

# A later change updates one occurrence and not the other. Both
# still run. Neither raises an error. The two limits have silently
# diverged, and nothing before this pointed at the fact that they
# were ever meant to be the same number in the first place.
```

A repeated literal is therefore a reliable, checkable proxy for
exactly the risk PYR203 is concerned with, even though it
does not capture every case a human reader would call magic. The `Final` closes
it the same way throughout this rule family, one named
declaration, every reference updated together, with mypy flagging
any attempt to later rebind it.

## Fix classification

**Kind:** `guidance`

**Reasoning:** The structural detection (a repeated literal) is
mechanical, but the fix itself still needs the same real naming
judgment as [PYR203](./PYR203-final-not-magic-numbers.md) — what to
call the extracted constant. PYR205 narrows *detection*, not the
naming difficulty the fix depends on.

## Severity

**Level:** `info`

**Reasoning:** Same reasoning as
[PYR203](./PYR203-final-not-magic-numbers.md): readability/maintainability
and drift prevention, not a silent-wrong-output risk.

## When this does not apply

- Two occurrences of the same number that are coincidentally equal
  but conceptually unrelated, for example an unrelated `2` used once
  as a list index and once as a multiplier elsewhere in the same
  file. Extracting a shared constant here would create a false,
  misleading connection between two values that were never meant to
  move together.
- Genuinely self-explanatory numbers with no meaningful name to give
  them, `0`, `1`, and `-1` used as plain arithmetic identities,
  indexes, or loop bounds, the same exemption PYR203 itself lists.

## Related

- [PYR203](./PYR203-final-not-magic-numbers.md) — the general form
  of this rule. PYR205 is the structurally detectable subset of it,
  independently adoptable, not a stricter or looser mode of the same
  rule.

## Enforced by

Not yet implemented.
