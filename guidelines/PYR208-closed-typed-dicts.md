# PYR208 — Declare a `TypedDict` closed unless deliberately open

## Rule

A `TypedDict` subclass must declare `closed=True` unless it is
deliberately consuming external or dynamic data whose extra keys are
a real, intended part of its contract.

```python
# Bad
class UserPayload(TypedDict):
    name: str
    email: str


# Good
class UserPayload(TypedDict, closed=True):
    name: str
    email: str
```

## Rationale

A `TypedDict` declared without `closed=True` (PEP 728, Python 3.15)
silently accepts extra keys beyond its own declared schema. Mypy does
not flag this:

```python
class UserPayload(TypedDict):
    name: str
    email: str


# A typo'd key, and an extra one. mypy passes this cleanly —
# every declared key is present with the right type, and TypedDict's
# own default openness says nothing about what else is allowed.
payload: UserPayload = {"name": "Ada", "emial": "ada@example.com", "role": "admin"}
```

This is exactly the class of bug pyrigor exists to catch: a
structurally unsound contract a type checker cannot see, because the
type system's own default behavior is the gap, not a missing check
layered on top of it. The `closed=True` makes the schema exhaustive —
any key not declared becomes a real type error, the typo included.

## Fix classification

**Kind:** `suggestion`

**Reasoning:** Adding `closed=True` is a one-token change, but it is
not always the correct one — a `TypedDict` that deliberately models
external or dynamic data (an API response with fields the author
does not fully control, a schema still growing) may need to stay
open on purpose. A human confirms the `TypedDict` is meant to be
exhaustive before the tool applies it, the same way
[PYR201](./PYR201-newtype-same-typed-values.md) needs a human to
confirm a guessed `NewType` name.

## Severity

**Level:** `warning`

**Reasoning:** A `TypedDict` accepting an unexpected extra key is a
real defect risk — a misspelled field passing silently, or a caller
relying on a key that was never actually part of the contract — but
it requires a caller to actually supply the wrong shape for the bug
to manifest, not a certainty on every declaration. Matches
[PYR402](./PYR402-keyword-only-arguments.md)'s own reasoning for
`warning` over `error`: real risk, narrower blast radius than a
confirmed, already-triggered bug class.

## Tier and maturity

**Tier:** `Default`

**Reasoning:** Closes a real, silent gap in `TypedDict`'s own default
behavior — consistent with pyrigor's core silent-bug mission, not an
opinionated preference.

**Maturity:** `Preview`

**Reasoning:** Python 3.15 introduced `closed=` (PEP 728), but
pyrigor supports Python 3.11 and later. Enforcement must wait until
pyrigor gains a real per-rule version-gating mechanism (see
#194/#195) — unlike [PYR207](./PYR207-frozen-constant-containers.md),
there is no partial, already-available half to enforce sooner.

## When this does not apply

- A `TypedDict` deliberately modeling external or dynamic data —
  a third-party API response, a schema still evolving, a case where
  openness is the correct, intended design, not an oversight. Use a
  suppression comment, `# pyrigor 208 # reason`, to record that this
  is a deliberate choice, not silently exempt it.
- A `TypedDict` defined outside the codebase pyrigor is checking is
  never in scope, matching PYR406's own established scoping.
- A `TypedDict` that already declares `closed=True` (or, once
  available, is otherwise structurally exhaustive) trivially does not
  match.

## Related

None yet.

## Enforced by

Not yet implemented.
