# PYR401 — Use `NamedTuple` for multi-value returns

## Rule

Any function returning more than one value must return a `NamedTuple`
rather than a plain `tuple`.

## Rationale

A function with a fully typed return annotation like `tuple[np.ndarray, float]`
is still vulnerable to a bug that no type checker catches: a caller can
unpack the result into misleadingly named variables, and as long as the
*types* line up positionally, the mismatch is silent.

```python
def compute_gradient(x: np.ndarray, y: np.ndarray, w: np.ndarray, b: float) -> tuple[np.ndarray, float]:
    ...
    return dj_dw, dj_db

# Silent bug: types match position-for-position, so mypy passes.
# The names are swapped, and nothing catches it until dj_dw_wrong is
# used somewhere its true type (float) breaks — e.g. calling .tolist()
# on what the caller believes is an ndarray.
dj_db_wrong, dj_dw_wrong = compute_gradient(x, y, w, b)
```

This is not a hypothetical — it reproduces any time a function’s
return order does not match a caller’s assumed order, particularly when
copying code between files or from reference material that uses a
different convention (for example `b, w` instead of `w, b`).

`NamedTuple` removes the positional slot as an attack surface. The caller
accesses fields by name, so there is nothing to mislabel:

```python
class GradientResult(NamedTuple):
    dj_dw: np.ndarray
    dj_db: float

def compute_gradient(x: np.ndarray, y: np.ndarray, w: np.ndarray, b: float) -> GradientResult:
    ...
    return GradientResult(dj_dw=dj_dw, dj_db=dj_db)

result = compute_gradient(x, y, w, b)
result.dj_db  # always the bias, regardless of unpacking order
result.dj_dw  # always the weights
```

## When this does not apply

- Single-value returns — nothing to unpack, rule is moot.
- Homogeneous, unbounded-length sequences (for example `tuple[float, ...]`) where
  the values are genuinely interchangeable by position, not distinct
  named quantities.
- Ephemeral local tuples created and unpacked in the same few lines,
  never crossing a function boundary.

## Related

- [PYR201](./PYR201-newtype-same-typed-values.md) — use `NewType` on
  `NamedTuple` fields (or function arguments) that share an underlying
  type and are at risk of being swapped even with named access.
- [PYR301](./PYR301-namedtuple-values.md) — the general form
  of this rule for bare tuple types anywhere other than a function
  signature (variables, dataclass fields, dict values).
- [PYR405](./PYR405-namedtuple-parameters.md) — the same
  rule applied to function parameters instead of return values.

## Enforced by

Not yet implemented.

## Detection scope

PYR401’s checker operates on return type annotations, not runtime
inference of what a function actually returns. A function with no
return annotation at all is outside this checker’s scope. The tool pyrigor
assumes mypy (or an equivalent type checker) is already enforcing
annotated returns project-wide and treats "no annotation" as a
separate, already-covered concern rather than something PYR401 needs
to detect itself.
