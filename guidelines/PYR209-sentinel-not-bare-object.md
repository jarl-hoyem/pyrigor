# PYR209 — Use the `sentinel` builtin, not a hand-rolled `object()` marker

## Rule

A module-level `object()` assignment used only for `is`/`is not` identity comparison, as a "no value provided" marker,
must use the `sentinel` builtin instead.

```python
# Bad
_MISSING = object()


def get(*, key: str, default: object = _MISSING) -> object:
    if default is _MISSING:
        ...


# Good
from sentinel import sentinel

_MISSING = sentinel("Missing")


def get(*, key: str, default: object = _MISSING) -> object:
    if default is _MISSING:
        ...
```

## Rationale

The `_MISSING = object()` idiom is common because Python had no dedicated type for it: any two calls to `object()` are
guaranteed distinct by identity, so it works as a unique marker. But a bare `object()` has no name at runtime — a
`repr()` of `_MISSING` prints `<object object at 0x...>`, useless in a debugger or traceback, and nothing distinguishes
one hand-rolled sentinel from another if two modules each define their own `_MISSING` and one is compared against the
other's constant by mistake, an `is` check that is always `False`, no error, no warning.

Python 3.15 adds a dedicated `sentinel` builtin (PEP 661) for exactly this pattern: a real, named, identity-unique
marker with a useful `repr()`, purpose-built rather than borrowed from `object()`'s own unrelated role as the base of
every class.

## Fix classification

**Kind:** `suggestion`

**Reasoning:** The tool can detect the shape (a module-level `object()` assignment used only in `is`/`is not`
comparisons) but cannot guarantee every `object()` instantiation is an identity marker rather than a genuine opaque
placeholder. A human confirms the intent before the fix is applied, the same reasoning
[PYR201](./PYR201-newtype-same-typed-values.md) already uses for a guessed name.

## Severity

**Level:** `info`

**Reasoning:** A hand-rolled sentinel is not a correctness bug in isolation — `object()`'s identity-uniqueness guarantee
is real and the pattern already works. This is a readability/debuggability and naming-consistency improvement, not a
silent-wrong-output risk, matching the template's own `info` example category.

## Tier and maturity

**Tier:** `Advisory`

**Reasoning:** A genuine, opinionated improvement over an already-safe idiom, not a silent-bug detector — the same shape
[PYR304](./PYR304-deque-for-queue-operations.md)'s opt-in reasoning uses. The `_MISSING = object()` is not a defect. The
`sentinel` builtin is simply a purpose-built alternative.

**Maturity:** `Preview`

**Reasoning:** Python 3.15 introduced the `sentinel` builtin (PEP 661), but pyrigor supports Python 3.11 and later.
Enforcement must wait until pyrigor gains a per-rule version gating mechanism (see #194/#195).

## When this does not apply

- An `object()` instantiation used as a genuine, deliberate opaque placeholder — not compared with `is`/`is not` as a
  "value not provided" marker at all. This rule only matches the identity-marker idiom specifically, not every
  `object()` call.
- A sentinel already expressed via an existing, established pattern with its own real justification (an `Enum` member
  used as a marker, for example) — a deliberate, different design choice, not an oversight this rule should override.
- A function or class defined outside the codebase pyrigor is checking is never in scope, matching PYR406's own
  established scoping.

## Related

None yet.

## Enforced by

Not yet implemented.
