# PYR502 — State implicit assumptions about inputs as explicit preconditions

## Rule

A function that assumes something about its inputs beyond what its
type annotations already guarantee. A specific shape, a matching
size between two arguments, a value within a range must state that
assumption as an explicit precondition check at the top of the
function body. Raising a clear exception if violated, rather than
leaving it implicit.

Use `raise`, not `assert`. Python's `-O` and `-OO` flags strip every
`assert` statement from compiled bytecode entirely, so a precondition
that matters is silently gone in an optimized build.

```python
# Bad
def compute_cost(*, x: np.ndarray, y: np.ndarray, w: Weight, b: Bias) -> float:
    # silently assumes x.shape == y.shape
    ...

# Bad — assert is stripped under python -O
def compute_cost(*, x: np.ndarray, y: np.ndarray, w: Weight, b: Bias) -> float:
    assert x.shape == y.shape, "x and y must have matching shapes"
    ...

# Good
def compute_cost(*, x: np.ndarray, y: np.ndarray, w: Weight, b: Bias) -> float:
    if x.shape != y.shape:
        raise ValueError("x and y must have matching shapes")
    ...
```

## Rationale

Type annotations describe the shape of a value’s type, `np.ndarray`,
`str`, `int`, but they cannot describe every assumption a function
actually depends on to behave correctly. The term `x: np.ndarray` says
nothing about what shape `x` must be, whether it must match some
other argument’s shape, or whether its values must fall within a
particular range. When a function relies on such an assumption
without stating it, the assumption still exists, invisible, living
only in the author’s head when the function was written.

```python
def compute_cost(*, x: np.ndarray, y: np.ndarray, w: Weight, b: Bias) -> float:
    # No check. If a caller passes mismatched shapes, this either
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
silently producing a wrong result. An explicit check at the top of
the function turns the assumption into something that runs at the
exact point it matters. With a message naming what was actually
expected, so a violation is caught immediately, at its true source,
rather than discovered later somewhere else entirely.

This is design-by-contract in miniature: state what a function
requires of its inputs as a real, enforced precondition, rather than
trusting every caller to already know and honor an assumption that
was never written anywhere.

**Why `raise`, not `assert`.** `assert` is the natural tool
for this, and earlier drafts of this guideline recommended it. It is
the wrong choice for anything that actually matters: Python's `-O`
flag removes every `assert` statement from the compiled bytecode
entirely, and `-OO` goes further. A precondition check written as
`assert` is not a weaker version of the check, it is no check at all
in an optimized build, silently.
<!-- @formatter:off -->
This is a real, known Python gap,
not a hypothetical one (see [OSSF’s Secure Coding Guide for Python,
pyscg-0037](https://github.com/ossf/wg-best-practices-os-developers/tree/main/docs/Secure-Coding-Guide-for-Python/08_coding_standards/pyscg-0037)).
`raise` with an explicit exception has no such gap, it runs
identically regardless of optimization flags.
<!-- @formatter:on -->

## When this does not apply

- The assumption is already fully captured by the type system itself,
  for example, a `NewType` or a `Literal` union that makes an invalid
  value impossible to build at all. A check that
  only restates that what mypy already guarantees adds no protection.
- A hot path where the check’s runtime cost has been measured to
  matter, and the precondition is instead enforced once, further
  upstream, at the point the value is first constructed or received.
- A genuinely internal, debug-only invariant, never reachable from
  untrusted input, where being silently skipped in an optimized
  build is an acceptable, deliberate trade-off. `assert` is the
  correct tool for exactly this narrower case, not for anything this
  rule is actually about.
- Checks that would trivially always pass given the type annotations
  already present, adding no real informational value over the
  annotation itself.

## Related

None yet.

## Enforced by

Not yet implemented.

### PYR502 recommends `assert`, which is stripped under Python’s -O flag

Found via OSSF’s Secure Coding Guide for Python (pyscg-0037,
"Presume Assertions May Be Disabled In Production"). Python's `-O`
and `-OO` optimization flags remove every `assert` statement from
compiled bytecode entirely. PYR502’s own doc recommends
`assert x.shape == y.shape, "..."` as its worked example, which
would silently vanish in an optimized build, exactly the kind of gap
this guide exists to catch.

The real fix needed, not just a note: PYR502 should recommend `if not
condition: raise ValueError(...)` for anything genuinely
correctness- or security-relevant, reserving `assert` only for
internal, debug-only invariants where being stripped in production
is acceptable. Needs its own decision about whether PYR502 should
distinguish these two cases explicitly (a "these are genuinely
different, use raise for one and assert for the other" rule) or
switch its own recommendation to raise-based checks entirely.
