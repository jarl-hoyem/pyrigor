# PYR501 — End a `match` over a closed set with `case _: assert_never(...)`

## Rule

A `match` statement over a value drawn from a closed set, most
commonly an `Enum` or a union of `Literal` types, must end with a
`case _:` branch that calls `typing.assert_never` on the matched
value.

```python
# Bad
match status:
    case ConvergenceStatus.RUNNING:
        ...
    case ConvergenceStatus.CONVERGED:
        ...
    case ConvergenceStatus.MAX_ITERS_REACHED:
        ...

# Good
from typing import assert_never

match status:
    case ConvergenceStatus.RUNNING:
        ...
    case ConvergenceStatus.CONVERGED:
        ...
    case ConvergenceStatus.MAX_ITERS_REACHED:
        ...
    case _:
        assert_never(status)
```

## Rationale

A `match` statement with no final catch-all branch compiles and runs
correctly right up until the closed set it matches against grows a
new member. The moment a new `Enum` value is added elsewhere in the
codebase, every existing `match` over that enum silently stops being
exhaustive. Any case that falls through the now-missing branch
does nothing at all, with no error, no warning, and no indication
anywhere a case was missed.

```python
class ConvergenceStatus(Enum):
    RUNNING = auto()
    CONVERGED = auto()
    MAX_ITERS_REACHED = auto()
    DIVERGED = auto()  # added later, elsewhere in the codebase

# This match statement, written before DIVERGED existed, still
# compiles and runs. If status is DIVERGED, none of the branches
# match, and the match statement completes having done nothing,
# with no exception raised.
match status:
    case ConvergenceStatus.RUNNING:
        ...
    case ConvergenceStatus.CONVERGED:
        ...
    case ConvergenceStatus.MAX_ITERS_REACHED:
        ...
```

A `case _: assert_never(status)` branch closes this gap in two
layers. At type-check time, mypy already understands
`assert_never`'s contract: if every other branch has narrowed the
`status` down to nothing remaining, the `case _:` branch is
statically proven unreachable, and mypy accepts it silently. The
moment a new enum member is added, and a branch for it is not,
mypy’s narrowing can no longer remove every possibility before
reaching `case _:`, and it raises a type error at the `assert_never`
call, at the exact `match` statement that needs updating, before the
code ever runs. At runtime, if this path is ever reached despite
that guarantee, for example, when an entirely different, untyped
data source produces an unexpected value, `assert_never` raises
immediately, rather than the `match` statement completing
silently having done nothing.

## Fix classification

**Kind:** `safe_fix`

**Reasoning:** A pure, non-displacing addition. If every real case
is already handled by an existing branch, the added `case _:
assert_never(...)` is unreachable by construction and mypy accepts
it silently. Per #105's own adopted classification.

## Severity

**Level:** `error`

**Reasoning:** A newly added case silently falls through as a no-op,
with nothing to indicate anything went wrong. See `DECISIONS.md`'s
"Severity" entry for the full per-rule reasoning.

## When this does not apply

- The value being matched is genuinely open-ended, not drawn from a
  closed, enumerable set (an arbitrary string, an unbounded numeric
  range), where there is no fixed set of cases to be exhaustive over.
- A deliberate default behavior is the correct response to any
  unmatched case, and that default is not to "silently do nothing." A
  `case _:` branch containing real fallback logic, rather than
  `assert_never`, is a legitimate design choice, just a different one
  than this rule addresses.

## Related

None yet.

## Enforced by

Not yet implemented.
