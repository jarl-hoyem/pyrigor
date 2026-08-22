# PYR303 — Iterate over a copy when the loop body may mutate the sequence

## Rule

Iterate over a copy of a list (or other mutable sequence) whenever
the loop body adds to or removes from that same sequence, never the
live original.

```python
# Bad
for item in orders:
    if item.is_cancelled:
        orders.remove(item)

# Good
for item in list(orders):
    if item.is_cancelled:
        orders.remove(item)
```

## Rationale

Removing an element from a list while iterating over it directly
silently skips the next element. The iterator's internal index
advances past whatever shifted into the removed position. This
produces a real, wrong result with no exception, no warning, and no
type error. It type-checks and runs cleanly. The bug only surfaces
as data, silently missing from the output.

## Fix classification

**Kind:** `safe_fix`

**Reasoning:** Wrapping the iterated sequence in `list(...)` (or an
equivalent copy) is unconditionally, mechanically safe. If the loop
body does not mutate the sequence, the copy is a harmless
no-op. If it does, this is exactly the correct fix. No design
judgment or naming decision is required.

## When this does not apply

- Iterating over a sequence, the loop body never mutates at all.
- A deliberate, already-safe pattern using `list.copy()` or a slice
  copy explicitly for this exact reason.

## Related

None yet.

## Enforced by

Not yet implemented.
