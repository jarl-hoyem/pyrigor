# PYR304 — Use `deque` for queue-style container operations

## Rule

A `list` used for repeated front-removal or front-insertion inside a loop (`some_list.pop(0)`,
`some_list.insert(0, value)`) must use `collections.deque` instead.

```python
# Bad
queue: list[int] = []
while pending:
    queue.pop(0)

# Good
from collections import deque

queue: deque[int] = deque()
while pending:
    queue.popleft()
```

## Rationale

A `list` is a contiguous array. Removing or inserting at the front means every remaining element has to shift by one
position — an O(n) operation, repeated on every iteration of a loop. A `collections.deque` is a double-ended queue,
backed by a structure that makes removal and insertion at _either_ end O(1). The code is correct either way. The `list`
version just does needless, repeated work that scales badly as the container grows.

This produces no wrong output and no exception — a case where mypy, pytest, and every existing pyrigor rule have nothing
to say, since none of them reason about algorithmic complexity. The bug (if a noticeably slow loop even gets traced back
to its actual cause) is a performance regression discovered late, not a correctness failure caught early.

## Fix classification

**Kind:** `suggestion`

**Reasoning:** Converting a `list` to a `deque` means changing the type at its _construction_ site, which may be far
from the flagged loop. The tool cannot confirm the same variable is never indexed or sliced elsewhere (`deque` supports
neither efficiently, and slicing not at all) without real data-flow analysis it does not have. A human confirms the
container is genuinely queue-shaped everywhere it is used, not just at the flagged line.

## Severity

**Level:** `info`

**Reasoning:** This is pyrigor's first rule that is not about a silent correctness bug — the existing three-level scale
was built entirely around that mission, and none of its levels were designed with performance in mind. `info`'s own
definition ("not a silent-wrong-output risk") is the least-wrong fit, since this rule's premise is correct output, just
slower. Worth revisiting as its own axis if a second performance rule ever needs the same treatment — not designed in
the abstract now for a single instance.

## Tier and maturity

**Tier:** `Advisory`

**Reasoning:** A real, genuine performance concern, but not pyrigor's core silent-bug mission — opt-in, the same way
#162's own walrus-ban motivating example was.

**Maturity:** `Preview`

**Reasoning:** Pyrigor's first rule in a genuinely new category (performance, not correctness). Worth some real-world
evidence before calling it `Stable`.

## When this does not apply

- `list.pop()` or `list.pop(-1)` (back-removal) and `list.append(x)` or `list.insert(len(x), value)` (back-insertion) —
  already O(1), never matches.
- A `.pop(0)`/`.insert(0, x)` call outside any loop — a one-off call's cost is negligible. This rule only fires on a
  call lexically nested inside a `for`/`async for`/`while`.
- A loop with a small, provably bounded iteration count, where the O(n) cost is genuinely negligible in practice. Not
  detectable automatically — use a suppression comment, `# pyrigor 304 # reason`, rather than expecting the rule to
  infer it.

## Related

- [PYR303](./PYR303-iterate-over-copy.md) — the other 3xx rule about the right way to manipulate a container inside a
  loop, though PYR303 is about correctness (skipped elements), not performance.

## Enforced by

Not yet implemented.
