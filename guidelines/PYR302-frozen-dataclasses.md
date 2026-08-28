# PYR302 — Use `frozen=True` for dataclasses holding structured state

## Rule

A `dataclass` whose instances represent a fixed piece of structured
state must be declared `@dataclass(frozen=True)`, unless mutation
after construction is a deliberate, documented part of its design.

```python
# Bad
@dataclass
class TrainingConfig:
    learning_rate: float
    max_epochs: int


# Good
@dataclass(frozen=True)
class TrainingConfig:
    learning_rate: float
    max_epochs: int
```

## Rationale

A plain, non-frozen `dataclass` is mutable by default. Any code
holding a reference to an instance can reassign any of its fields at
any time, from anywhere, with no indication at the point of
construction that this was ever intended to happen.

```python
config = TrainingConfig(learning_rate=0.01, max_epochs=100)
train_model(config=config)

# Deep inside some unrelated function, far from where config was
# built and far from where it is used again:
config.learning_rate = 0.5

# Every subsequent use of config now silently reflects a change made
# somewhere else entirely, with nothing at either the mutation site
# or the later read site indicating this happened.
```

This is the same class of problem [PYR401](./PYR401-namedtuple-returns.md)
and [PYR301](./PYR301-namedtuple-values.md) address for tuples,
applied to `dataclass` instead. Structured data that is meant to
represent a single, fixed snapshot of the state should not be silently
mutable. Because every place that reads it has to additionally
reason about every other place that might have changed it, rather than
being able to trust the value once constructed.

`frozen=True` makes any attempted mutation a runtime `FrozenInstanceError`,
immediately, at the point the mutation is attempted, rather than a
silent write that only surfaces as a bug somewhere else later.

## Fix classification

**Kind:** `suggestion`

**Reasoning:** Adding `frozen=True` is a concrete, previewable
one-line change, but this rule's own "When this does not apply"
section names a common, legitimate exception, a dataclass
deliberately designed to accumulate or update state. The tool cannot
tell that case apart from an oversight without a human confirming
the class's actual intended mutability, so this sits at suggestion,
not safe fix, despite the mechanical simplicity of the change itself.

## Severity

**Level:** `warning`

**Reasoning:** Prevents accidental mutation — real, but narrower
blast radius than a genuinely silent correctness bug. See
`DECISIONS.md`'s "Severity" entry for the full per-rule reasoning.

## When this does not apply

- A `dataclass` whose entire purpose is to accumulate or update state
  over its lifetime, such as a counter, an in-progress builder object,
  or a mutable cache entry, where mutation is the intended, primary
  use case rather than an accident.
- Fields that genuinely need in-place mutation for performance reasons
  in a hot path, where reconstructing a new frozen instance on every
  update has been measured to matter.

## Related

- [PYR401](./PYR401-namedtuple-returns.md) and
  [PYR301](./PYR301-namedtuple-values.md) — the same underlying
  concern, unnamed or unstructured mutability risk, addressed for
  tuples rather than dataclasses.
- [PYR404](rejected/PYREJECT101-immutable-defaults.md) — a related but distinct
  concern: a mutable default argument value shared across calls,
  rather than a mutable field on a constructed instance.

## Enforced by

Not yet implemented.
