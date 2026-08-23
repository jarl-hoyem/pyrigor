# PYR402 — Force keyword-only arguments for all parameters

## Rule

All function parameters beyond `self`/`cls` must be keyword-only —
enforced with a bare `*` at the start of the parameter list. This
applies even when every argument has a distinct type and even when
[PYR201](PYR201-newtype-same-typed-values.md) is already in use.

```python
# Bad
def compute_gradient(x: np.ndarray, y: np.ndarray, w: Weight, b: Bias) -> GradientResult:
    ...

# Good
def compute_gradient(*, x: np.ndarray, y: np.ndarray, w: Weight, b: Bias) -> GradientResult:
    ...
```

## Rationale

[PYR201](PYR201-newtype-same-typed-values.md) makes same-typed values
nominally distinct, and to be precise about what that buys you: if
both values are wrapped at their point of origin and that
distinction survives to the call site, mypy *does* catch a positional
swap, the same way it catches any other type mismatch.

```python
Weight = NewType("Weight", float)
Bias = NewType("Bias", float)

def apply_correction(weight: Weight, bias: Bias) -> float:
    ...

# mypy catches this: bias_value is typed Bias, first parameter expects
# Weight. PYR201 alone is sufficient here, *if* every value in the
# chain retained its NewType through to this call.
apply_correction(bias_value, weight_value)
```

So PYR402 is not closing a static-type blind spot PYR201 leaves open —
it is addressing three things PYR201’s protection is
*contingent* on, plus one PYR201 cannot address at all:

**1. Mypy has to actually run, and has to see the chain.**
`NewType` protection is static-only. If a value is unwrapped for
arithmetic and not rewrapped, passed through a `dict`, returned from
an untyped or `Any`-leaking function, or reaches this call from any
code path mypy does not fully analyze, the
distinction is lost. The swap becomes invisible again —
with no warning protection has degraded. Keyword-only arguments
raise a `TypeError` at the language level, independent of whether
mypy ran, and independent of whether type distinction survived intact
up to this point.

**2. Signature reordering.** If `apply_correction`'s parameters are
later reordered during a refactor (`bias` moved before `weight`, say),
every existing positional call site is now wrong — and if the caller
also happens to pass differently ordered but correctly typed values,
mypy sees a swap and catches it. But if the reordering coincides with
how the caller already listed the values, nothing catches it at all,
because both are now "correct" relative to the new signature by
coincidence. Keyword calls are immune to this entire class of bugs:
binding is by name, so a parameter reorder in the function definition
cannot corrupt any existing call site.

**3. Differently typed arguments get the same protection for free.**
PYR201 only applies where confusion between same-typed values is
plausible. PYR402 applies uniformly to every parameter, so the
signature-reordering protection in point 2 above holds regardless of
whether PYR201 was ever relevant to this particular function.

**4. Human readability at the point of writing.**
Even where mypy would eventually catch a mistake, a keyword-only call site
states its own argument mapping in plain text — both when it is written
and every time it is read again later. That is closer to design-by-contract
than relying on a type-checker run to surface the error after the fact.

None of this makes [PYR201](PYR201-newtype-same-typed-values.md)
redundant — `NewType` still gives mypy the chance to catch a bare,
unwrapped value landing in the wrong slot, which keyword-only calling
alone does not. A keyword call with the *wrong keyword name* used by
mistake is still a real, if less common, way to swap values. PYR402
is defense in depth: a language-level guarantee that holds even when
the static-analysis guarantee’s preconditions are not met.

Combined with [PYR401](PYR401-namedtuple-returns.md) and
[PYR201](PYR201-newtype-same-typed-values.md), this closes the
remaining gaps in the full picture:

- Argument-order swaps for differently typed args → plain type
  annotations catch a type mismatch. PYR402 adds robustness against
  signature reordering and against mypy not running.
- Argument-order swaps for same-typed args → `NewType`
  (PYR201) catches it *when* type distinction survives to the call
  site. PYR402 adds the same robustness on top.
- Return-unpacking mislabeling for differently typed return values →
  `NamedTuple` (PYR401)
- Return-unpacking mislabeling for same-typed return fields →
  `NamedTuple` + `NewType` (PYR401 + PYR201)

## Fix classification

**Kind:** `safe_fix`

**Reasoning:** Mechanical and correct. Any caller consequence is
immediate and loud, via mypy/pyright flagging a positional argument
against a keyword-only parameter as a hard type error, not a silent
behavior change. Per #105's own adopted classification.

## When this does not apply

- Single-parameter functions, where there is no argument order to
  confuse. See [PYR403](./PYR403-keyword-only-single-argument.md) for
  a separate, independently adoptable rule covering this case under a
  different rationale.
- Well-established positional conventions from the standard library or
  a widely used third-party API that this codebase wraps or extends,
  where keyword-only would fight the convention callers already expect
  (for example, extending a `dataclass`-generated `__init__`).
- Hot code paths where the (typically negligible) overhead
  of keyword argument binding has been profiled and shown to matter —
  rare, and should be justified with a comment at the call site if
  invoked.

## Related

- [PYR401](PYR401-namedtuple-returns.md) — use `NamedTuple` for any
  function returning more than one value.
- [PYR201](PYR201-newtype-same-typed-values.md) — use `NewType` for
  same-typed values at risk of being swapped. PYR402 closes the
  residual call-site-ordering gap that PYR201 alone does not.

## Enforced by

The `pyr402` checker (`pyrigor/checkers/pyr402_keyword_only_arguments.py`),
wired in as a pre-commit hook and available via the `pyrigor` CLI
(`pip install pyrigor`, then `pyrigor path/to/file.py`).
