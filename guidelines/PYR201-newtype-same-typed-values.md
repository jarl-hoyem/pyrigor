# PYR201 — Use `NewType` for same-typed values at risk of being swapped

## Rule

Two or more separate, individually named parameters or `NamedTuple` fields, within a locally defined function or class,
that share an identical bare type annotation, must use distinct `NewType` wrappers rather than the bare underlying type.

## Rationale

Different-typed arguments are already protected by mypy: a swap at the call site is a type mismatch and gets caught.

```python
def compute_gradient(x: np.ndarray, y: np.ndarray, w: np.ndarray, b: float) -> ...: ...


# Swapping w and b here is a type error — mypy catches it, nothing to add.
compute_gradient(x, y, b, w)  # error: expected ndarray, got float
```

Same-typed arguments are not protected by mypy alone. Two `float` parameters are structurally identical, so a swap is a
silent, valid-looking call:

```python
def apply_correction(weight: float, bias: float) -> float: ...


# Both floats. Types line up. mypy passes. The values are swapped.
apply_correction(bias, weight)
```

`NewType` makes same-typed-but-semantically-distinct values nominally distinct, so mypy catches the swap:

```python
from typing import NewType

Weight = NewType("Weight", float)
Bias = NewType("Bias", float)


def apply_correction(weight: Weight, bias: Bias) -> float: ...


apply_correction(bias, weight)  # error: expected Weight, got Bias
```

This is not redundant with [PYR401](PYR401-namedtuple-returns.md). `NamedTuple` closes the _return-unpacking_ gap — it
stops a caller from mislabelling fields by position. But if a `NamedTuple`'s fields are still bare same-typed values,
two fields can still be constructed in the wrong order at the point the `NamedTuple` itself is built, or passed to a
function expecting them in a different arrangement, without any type error:

```python
class GradientResult(NamedTuple):
    dj_dw: float
    dj_db: float


# Both floats — named access alone doesn't stop this from compiling
# with the values swapped at construction time.
GradientResult(dj_dw=dj_db_value, dj_db=dj_dw_value)
```

`NewType` on the fields themselves closes that remaining gap:

```python
Weight = NewType("Weight", float)
Bias = NewType("Bias", float)


class GradientResult(NamedTuple):
    dj_dw: Weight
    dj_db: Bias


def compute_gradient_logistic(x: np.ndarray, y: np.ndarray, w: Weight, b: Bias) -> GradientResult:
    ...
    return GradientResult(dj_dw=dj_dw, dj_db=dj_db)
```

Combined, [PYR401](./PYR401-namedtuple-returns.md) and PYR201 catch:

- Argument-order swaps for differently typed args → plain type annotations (no extra tooling needed)
- Argument-order swaps for same-typed args → `NewType`
- Return-unpacking mislabelling for differently typed return values → `NamedTuple` alone
- Return-unpacking mislabelling for same-typed return fields → `NamedTuple` + `NewType` together

`NewType` has zero runtime cost — it is an identity function at runtime, purely a mypy-time construct — so there is no
performance argument against using it wherever confusion is plausible.

## Fix classification

**Kind:** `suggestion`

**Reasoning:** The tool can propose a specific, previewable `NewType` wrapper and even guess plausible names from the
parameter or field names involved, but it cannot guarantee the guessed name is the correct domain concept — a human
confirms the design choice. Per #105's own adopted classification.

## Severity

**Level:** `warning`

**Reasoning:** Prevents same-typed-value confusion but requires the swap to actually occur. See `DECISIONS.md`'s
"Severity" entry for the full per-rule reasoning.

## When this does not apply

- A homogeneous collection of same-typed values (for example, `list[float]` sensor readings) never matches this rule at
  all. It is not expressed as separate, individually named parameters or fields. Structurally excluded, not a judgment
  call.
- A function or class defined outside the codebase pyrigor is checking is never in scope, matching PYR406's own
  established scoping. A third-party API's own unwrapping cost is never pyrigor's call to make.
- A single occurrence of a type, with no sibling of the same type nearby, is mechanically excluded by the "two or more"
  count itself.
- Any remaining, genuine exception, use a suppression comment, `# pyrigor: 201 # reason`, rather than expecting the rule
  to infer it automatically.

## Related

- [PYR401](PYR401-namedtuple-returns.md) — use `NamedTuple` for any function returning more than one value. PYR401 and
  PYR201 are complementary: PYR401 removes positional-unpacking ambiguity, PYR201 removes same-type confusion that named
  access alone does not catch.

## Enforced by

Not yet implemented.
