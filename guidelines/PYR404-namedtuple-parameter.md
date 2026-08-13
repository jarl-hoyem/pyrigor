# PYR405 — Use `NamedTuple` for multi-value parameter types, not bare `tuple`

## Rule

A function parameter typed as a bare, fixed-length `tuple` (for
example `tuple[int, int]`) must use a `NamedTuple` type instead.

```python
# Bad
def step_bot(*, action: tuple[int, int]) -> None:
    row, col = action
    ...

# Good
class BotAction(NamedTuple):
    row: int
    col: int

def step_bot(*, action: BotAction) -> None:
    ...
```

## Rationale

This is [PYR401](./PYR401-namedtuple-returns.md)’s failure mode on the
other side of the function boundary. PYR401 stops a function from
*returning* a positionally ambiguous multi-value tuple; PYR405 stops a
function from *accepting* one as a parameter.

```python
def step_bot(*, action: tuple[int, int]) -> None:
    row, col = action
    ...

# Is this (row, col) or (col, row)? Nothing in the type or the call
# site says. Both orderings type-check identically.
step_bot(action=(3, 7))
```

[PYR402](./PYR402-keyword-only-arguments.md) forces `action` itself to
be passed by keyword, but that only protects the outer call — it does
nothing for the two `int`s living inside the tuple. Once you’re past
`action=`, the ambiguity PYR401 was written to eliminate on returns is
right back, just moved to the input side.

`NamedTuple` closes it the same way it does for returns: named field
access removes the positional slot as an attack surface, both at
construction (`BotAction(row=3, col=7)`, unambiguous) and at use
(`action.row`, `action.col`, no unpacking order to get wrong).

## When this does not apply

- Genuinely homogeneous, order-independent, or unbounded-length tuples
  (`tuple[float, ...]`), where there is no fixed positional meaning to
  get wrong.
- A tuple parameter matching an external API’s expected shape
  (numpy/library conventions, a fixed C-extension calling convention)
  where introducing a `NamedTuple` wrapper would require constant
  unwrapping at the boundary with the library.

## Related

- [PYR401](./PYR401-namedtuple-returns.md) — the same rule applied to
  function return values instead of parameters.
- [PYR301](./PYR301-namedtuple-not-bare-tuple.md) — the general form
  of this rule for bare tuple types anywhere other than a function
  signature (variables, dataclass fields, dict values).
- [PYR402](./PYR402-keyword-only-arguments.md) — forces the parameter
  itself to be passed by keyword; complementary, not a substitute —
  PYR402 protects the outer call, PYR405 protects what’s inside the
  tuple.

## Enforced by

Not yet implemented.