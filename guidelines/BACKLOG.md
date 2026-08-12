# MISRA-Style Rigor in Python — Habits to Build Over Time

Reference notes from the ML course sessions. Not urgent — revisit and adopt gradually.

## 1. Never use direct float equality

```python
# Bad
converging = (cost - new_cost) == 0

# Good
converging = abs(cost - new_cost) < 1e-12
```

Floats rarely land exactly on a value due to rounding. This is a real latent bug pattern, not just style.

## 2. `Final` for values that should never be reassigned

```python
from typing import Final

LEARNING_RATE: Final = 0.001
```

The mypy errors, if anything, later tries to rebind it.

## 3. Frozen structures for all multi-field states

Use `NamedTuple` or `@dataclass(frozen=True)` for any structured data passed around — not just function returns. Nothing
should be mutable after construction unless it needs to be.

## 4. `Enum` instead of magic strings/bools for state

```python
from enum import Enum, auto

class ConvergenceStatus(Enum):
    RUNNING = auto()
    CONVERGED = auto()
    MAX_ITERS_REACHED = auto()
```

Prevents typos like `"convergd"` from doing nothing silently. The tool mypy catches invalid members.

## 5. Keep mypy `--strict`, resist `Any` leaking in

Already in use — every `no-any-return` error caught this session is exactly this discipline working.

## 6. Never use mutable default arguments

_Planned as PYR404._

```python
# Bad — shared mutable state across every call
def f(items: list = []):
    ...

# Good
def f(items: list | None = None):
    items = items if items is not None else []
```

## 7. `assert_never` for exhaustiveness checking

```python
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

If a new enum member is added later, and a branch is missed, mypy flags it at type-check time.

## 8. Explicit precondition checks, not implicit trust

```python
def compute_cost(*, x: np.ndarray, y: np.ndarray, w: Weight, b: Bias) -> float:
    assert x.shape == y.shape, "x and y must have matching shapes"
    ...
```

Design-by-contract style: state assumptions explicitly rather than assuming callers behave.

## 9. No wildcard imports

```python
# Bad
from utils import *

# Good
from utils import load_data, load_data_multi
```

Never let names enter the scope invisibly.

## 10. `NewType` for domain-distinct values sharing the same underlying type

Already applied in `ml_types.py` (`Weight`, `Bias`). Zero runtime cost, but mypy treats them
as distinct types — catches swaps that keyword arguments alone cannot (for example, passing a `Bias`
where a `Weight` is expected, even with correct keyword syntax).

## Elaboration on 3 and 10

NamedTuple for returns, NewType for same-typed values at risk of confusion.

Rule:

Always use NamedTuple for any function returning more than one value. This removes positional-unpacking ambiguity — the
caller accesses fields by name (result.dj_dw), not position, so a mislabeled variable at the call site can no longer
silently receive the wrong value.
Use NewType for any same-typed values — whether function arguments or NamedTuple fields — that could plausibly be
swapped or confused (for exampleWeight/Bias when both might be represented as float or same-shaped ndarray). Skip it
where
confusion isn't realistically possible.

Why:

Different-typed arguments (for example, w: np.ndarray, b: float) are already protected by mypy — a swap at the call
site is a
type mismatch and gets caught. No NewType needed here.
Same-typed arguments (for example, two float parameters) are not protected by mypy alone — both are structurally
identical, so a
swap is a silent, valid-looking call. NewType makes them nominally distinct, so mypy catches the swap.
NamedTuple closes a separate gap: even with a fully typed multi-value return (for example, tuple[np.ndarray, float]),
mypy
checks the type at each position but not the name the caller gives it. A caller can unpack into misleadingly named
variables (dj_db_temp, dj_dw_temp = ... when the function actually returns dj_dw, dj_db), and mypy will not catch it,
because the types still line up positionally — only the semantics are wrong. This is a silent bug that surfaces only
when the mislabeled variable is later used in a way that exposes its true type (for example, calling .tolist() on
what you
thought was a float), which is a runtime crash, not a caught error.
NamedTuple field access removes the positional slot entirely, so there's nothing to mislabel.

Combined, these two will catch:

Argument-order swaps for differently typed args → plain type annotations (no extra tooling needed)
Argument-order swaps for same-typed args → NewType
Return-unpacking mislabeling for differently typed return values → NamedTuple alone
Return-unpacking mislabeling for same-typed return fields → NamedTuple + NewType together.

Example:

```python
class GradientResult(NamedTuple):
dj_dw: Weight
dj_db: Bias

def compute_gradient_logistic(x: np.ndarray, y: np.ndarray, w: Weight, b: Bias) -> GradientResult:
...
return GradientResult(dj_dw=dj_dw, dj_db=dj_db)
```

---

**Suggested order to actually adopt these, when ready:**

1. Fix float equality (#1) — real bug risk, quick win
2. `Final` for constants (#2) — nearly free
3. No wildcard imports (#9) — mechanical fix
4. No mutable defaults (#6) — mechanical fix
5. Everything else, as the codebase grows, and the payoff becomes clearer.
