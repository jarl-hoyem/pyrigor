# PYR502 — State implicit assumptions about inputs as explicit preconditions

## Rule

A function that assumes something about its inputs beyond what its
type annotations already guarantee, a specific shape, a matching
size between two arguments, a value within a range, must state that
assumption as an explicit `assert` at the top of the function body,
rather than leaving it implicit.

```python
# Bad
def compute_cost(*, x: np.ndarray, y: np.ndarray, w: Weight, b: Bias) -> float:
    # silently assumes x.shape == y.shape
    ...

# Good
def compute_cost(*, x: np.ndarray, y: np.ndarray, w: Weight, b: Bias) -> float:
    assert x.shape == y.shape, "x and y must have matching shapes"
    ...
```

## Rationale

Type annotations describe the shape of a value’s type, `np.ndarray`,
`str`, `int`, but they cannot describe every assumption a function
actually depends on to behave correctly. The term `x: np.ndarray` says
nothing about what shape `x` must be, whether it must match some
other argument’s shape, or whether its values must fall within a
particular range. When a function relies on such an assumption
without stating it, the assumption still exists. The assumption is
invisible, living only in the author’s head, when the function
was written.

```python
def compute_cost(*, x: np.ndarray, y: np.ndarray, w: Weight, b: Bias) -> float:
    # No assertion. If a caller passes mismatched shapes, this either
    # raises a low-level numpy broadcasting error somewhere deep
    # inside the arithmetic, far from the actual mistake, or worse,
    # silently broadcasts to an unintended shape and returns a wrong
    # answer with no error at all.
    ...
```

An unstated assumption fails in one of two ways, both worse than a
clear, immediate error. It either propagates until some unrelated
piece of code downstream breaks in a way that gives no clue about
the actual, distant cause, or it does not visibly fail at all,
silently producing a wrong result. An explicit `assert` at the top of
the function turns the assumption into a check that runs at the
exact point it matters, with a message that names what was actually
expected, so a violation is caught immediately, at its true source,
rather than discovered later somewhere else entirely.

This is design-by-contract in miniature: state what a function
requires of its inputs as a real, checked precondition, rather than
trusting every caller to already know and honor an assumption that
was never written anywhere.

## When this does not apply

- The assumption is already fully captured by the type system itself,
  for example, a `NewType` or a `Literal` union that makes an invalid
  value impossible to create. An `assert` that
  only restates what mypy already guarantees adds no protection.
- A hot path where the assertion’s runtime cost has been measured to
  matter, and the precondition is instead enforced once, further
  upstream, at the point the value is first constructed or received.
- Assertions that would trivially always pass given the type
  annotations already present, adding no real informational value
  over the annotation itself.

## Related

None yet.

## Enforced by

Not yet implemented.
