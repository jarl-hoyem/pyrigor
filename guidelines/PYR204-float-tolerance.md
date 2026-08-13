# PYR204 — Use tolerance-based comparison for floats, never `==`

## Rule

Two floating-point values must never be compared with `==` or `!=`.
Use `math.isclose`, or an explicit tolerance check, instead.

```python
# Bad
if cost - previous_cost == 0:
    converged = True

# Good
import math

if math.isclose(cost, previous_cost, abs_tol=1e-12):
    converged = True
```

## Rationale

Floating-point arithmetic does not represent most real numbers
exactly. Two values that are mathematically equal, or that a
calculation intends to be equal, routinely differ by a tiny rounding
error after any arithmetic is performed on them. Because the
underlying binary representation cannot exactly store the most decimal
fractions.

```python
result = 0.1 + 0.2
result == 0.3
# False. result is actually 0.30000000000000004.
```

A direct equality check against a float is therefore not
checking "are these the same value." It is checking "did this exact
sequence of arithmetic operations happen to produce a "bit-identical"
result," which is a much narrower and less useful question. Usually not
the question the code actually meant to ask. The most
common real consequence is a convergence or termination check that
never fires, or fires inconsistently depending on unrelated changes
elsewhere in a calculation. Because the values being compared are
"close enough" by any reasonable standard but not bit-identical.

`math.isclose` (or an equivalent explicit tolerance) makes the actual
intent, "these are the same within an acceptable margin," the thing
that is actually checked, rather than relying on exact bitwise
equality that floating-point arithmetic cannot reliably guarantee.

## When this does not apply

- Comparing a float against a sentinel value that is guaranteed to be
  exact by construction, most commonly comparing against a literal
  `0.0` or `float("inf")` that was never the result of arithmetic,
  only ever assigned directly.
- Checking whether two float variables refer to the identical object
  (`is`, not `==`), which is a different, unrelated question.

## Related

None yet.

## Enforced by

Not yet implemented.
