# PYR207 — Use a frozen container for a module-level constant dict or set

## Rule

A module-level `dict` or `set` literal that is assigned once and never reassigned or mutated anywhere else in the file
must use `frozendict`/`frozenset` instead of the mutable builtin.

```python
# Bad
VALID_STATUSES = {"pending", "active", "closed"}
RETRY_DELAYS = {1: 0.5, 2: 1.0, 3: 2.0}

# Good
VALID_STATUSES: frozenset[str] = frozenset({"pending", "active", "closed"})
RETRY_DELAYS: frozendict[int, float] = frozendict({1: 0.5, 2: 1.0, 3: 2.0})
```

## Rationale

`Final` (see [PYR203](./PYR203-final-not-magic-numbers.md)/ [PYR205](./PYR205-final-constants.md)) stops a name from
being rebound to a new object. It says nothing about the object that name already points to. A module-level `dict`/`set`
meant to be a constant lookup table is still fully mutable at every call site that imports it:

```python
from mymodule import VALID_STATUSES

# Final on VALID_STATUSES, if it had it, would not stop this.
# Every other importer of VALID_STATUSES now silently sees the change.
VALID_STATUSES.add("archived")
```

This is a real, silent shared-mutable-state bug, not hypothetical: the Mutation happens in one file, and its effect is
visible everywhere else that already imported the same object, with no error and no indication at the mutation site that
anything module-scoped changed. Mypy and Ruff both pass this cleanly — a `dict`/`set` is exactly as mutable as its own
type declares, nothing about the annotation `dict[str, float]` claims otherwise.

`frozendict`/`frozenset` make the mutation impossible rather than merely unconventional. `VALID_STATUSES.add(...)` on a
`frozenset` is not a runtime surprise, it is a `mypy`/`pyright` error at the call site, caught immediately, the same way
[PYR402](./PYR402-keyword-only-arguments.md)'s keyword-only rewrite turns a silent positional-argument risk into an
immediate type error instead.

## Fix classification

**Kind:** `safe_fix`

**Reasoning:** Wrapping a `dict`/`set` literal in `frozendict`/ `frozenset` preserves every read operation (indexing,
`.get()`, `in`, iteration) identically. The only capability removed is a mutation, which the rule already confirmed does
not happen anywhere in the file. Any place that assumed mutability fails at the type-checker, not silently at runtime.

## Severity

**Level:** `warning`

**Reasoning:** An accidental mutation of a constant, module-level container is a real, silent correctness bug when it
happens — shared state drifting for every other importer, with no error at the mutation site. This rule is prophylactic:
it never requires the mutation to have actually occurred, and once applied, any attempted mutation becomes an immediate
type-checker error rather than a silent one, the same reasoning
[PYR402](./PYR402-keyword-only-arguments.md)/[PYR403](./PYR403-keyword-only-single-argument.md) already use for
`warning` over `error`.

## Tier and maturity

**Tier:** `Default`

**Reasoning:** Prevents a real, silent shared-state bug, consistent with pyrigor's core mission — not an opinionated
preference someone might reasonably reject the way [PYR304](./PYR304-deque-for-queue-operations.md)'s performance
concern is.

**Maturity:** `Preview`

**Reasoning:** `frozendict` does not exist before Python 3.15 (PEP 814), but pyrigor supports Python 3.11 and later.
Enforcement must wait until pyrigor gains per-rule version gating (see #194/#195). `frozenset` half of this rule has no
such blocker — already available on 3.11+ — so enforcement may land in two phases, one gated and one not, a decision
left for implementation time.

## When this does not apply

- A container built incrementally — populated across multiple statements, for example, inside a loop — and never
  modified after that point. This rule matches a single literal assignment which is never modified later in the file.
  Mutation during construction is itself a mutation, so the rule excludes it structurally rather than missing it.
- A container that is genuinely, deliberately reassigned under a condition (for example, a different lookup table per
  environment). Reassignment already excludes it from "assigned once."
- A function or class defined outside the codebase pyrigor is checking is never in scope, matching PYR406's own
  established scoping.
- Any remaining, genuine exception — use a suppression comment, `# pyrigor 207 # reason`, rather than expecting the rule
  to infer it automatically.

## Related

- [PYR203](./PYR203-final-not-magic-numbers.md) and [PYR205](./PYR205-final-constants.md) — the `Final`-constant family
  closes the _rebinding_ gap for a name. PYR207 closes the _mutation_ gap for the object referenced by a container-typed
  name. already points to, which `Final` alone does not address.

## Enforced by

Not yet implemented.
