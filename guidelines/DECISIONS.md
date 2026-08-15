# Design and architecture decisions

A running log of *why* a structural choice was made, not just the
result. Read this before asking "why does the code do it this way"
rather than re-deriving the reasoning from scratch.

## NamedTuple and NewType close different gaps

NamedTuple for returns, NewType for same-typed values at risk of confusion.

Rule:

Always use NamedTuple for any function returning more than one
value. This removes positional-unpacking ambiguity. The caller
accesses fields by name (result.dj_dw), not position, so a
mislabeled variable at the call site can no longer silently receive
the wrong value.

Use NewType for any same-typed values, whether function arguments or
NamedTuple fields, that could plausibly be swapped or confused (for
example, Weight/Bias when both might be represented as float or a
same-shaped ndarray). Skip it where confusion is not realistically
possible.

Why:

Different-typed arguments (for example, w: np.ndarray, b: float) are
already protected by mypy, a swap at the call site is a type
mismatch and gets caught. No NewType needed here.

Same-typed arguments (for example, two float parameters) are not
protected by mypy alone. Both are structurally identical, so a swap
is a silent, valid-looking call. NewType makes them nominally
distinct, so mypy catches the swap.

NamedTuple closes a separate gap: even with a fully typed
multi-value return (for example, tuple[np.ndarray, float]), mypy
checks the type at each position but not the name the caller gives
it. A caller can unpack into misleadingly named variables
(dj_db_temp, dj_dw_temp = ... when the function actually returns
dj_dw, dj_db), and mypy will not catch it, because the types still
line up positionally, only the semantics are wrong. This is a silent
bug that surfaces only when the mislabeled variable is later used in
a way that exposes its true type. For example, calling '.tolist()' on
an assumed float, a runtime crash, not a caught error.

NamedTuple field access removes the positional slot entirely, so
there is nothing to mislabel.

Combined, these two will catch:

- Argument-order swaps for differently typed args: plain type
  annotations (no extra tooling needed).
- Argument-order swaps for same-typed args: NewType.
- Return-unpacking mislabeling for differently typed return values:
  NamedTuple alone.
- Return-unpacking mislabeling for same-typed return fields:
  NamedTuple and NewType together.

Example:

```python
class GradientResult(NamedTuple):
    dj_dw: Weight
    dj_db: Bias

def compute_gradient_logistic(x: np.ndarray, y: np.ndarray, w: Weight, b: Bias) -> GradientResult:
    ...
    return GradientResult(dj_dw=dj_dw, dj_db=dj_db)
```
