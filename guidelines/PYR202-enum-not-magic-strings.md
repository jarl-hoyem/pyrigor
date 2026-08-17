# PYR202 — Use `Enum` instead of magic strings, ints, or bools for closed sets of states.

## Rule

Any value that represents one of a fixed, known set of states must be
an `Enum` member, not a bare string, integer, or boolean standing in
for that state.

```python
# Bad
status = "converged"

# Good
from enum import Enum, auto

class ConvergenceStatus(Enum):
    RUNNING = auto()
    CONVERGED = auto()
    MAX_ITERS_REACHED = auto()

status = ConvergenceStatus.CONVERGED
```

## Rationale

A bare string used as a state marker has no protection against typos.
`"convergd"` is a different string from `"converged"`, and nothing —
not Python itself, not mypy — flags the difference. The mistake is
silent: the comparison `status == "converged"` evaluates to
`False` forever, and the program continues running with the wrong
branch taken, with no exception, no warning, nothing to indicate
anything went wrong at all.

```python
status = "convergd"  # typo

if status == "converged":
    ...  # never runs — and nothing ever tells you why
```

An `Enum` closes this. Whereas `ConvergenceStatus.CONVERGD` does not exist, so
the typo becomes an `AttributeError` at the point it is written, not a
silent no-op discovered later:

```python
status = ConvergenceStatus.CONVERGD  # AttributeError: no such member
```

This is the same failure shape as
[PYR201](./PYR201-newtype-same-typed-values.md)'s same-typed-value
confusion, one level further out: instead of two structurally
identical types being interchangeable when they should not be, here
it is an *unbounded* type (any `str`, any `int`) standing in for a
value that should only ever be one of a small, closed set. An `Enum`
makes the set of valid values a real, checkable type, rather than a
convention every caller has to remember and get exactly right.

This matches [PEP 435](https://peps.python.org/pep-0435/)’s own
stated motivation for adding `enum` to Python itself. It frames the
same problem: a plain `int` or `str` can represent discrete
values well enough, but nothing stops "operations without meaning
('Wednesday times two')" from being defined on them. Nothing keeps
a value from one enumeration distinct from a value in another,
either. An `Enum` closes both gaps at once — the same distinctness
argument PYR201 makes for two same-typed values, applied here to a
value standing in for one of several unrelated named states.

**The same failure is more common at boundaries than inside a
program’s own logic.** A value arriving from JSON, a CSV file, a form
field, a database row, or an environment variable is stringly-typed
by construction — `"42"`, `"true"`, `"converged"` — regardless of
what it conceptually represents. If that value is used as-is, without
converting it into the type it actually represents at the point it
enters the program, every one of its bugs (a typo’d status string, a
`"0"`/`"1"` standing in for a boolean, a numeric ID compared against a
string) is deferred to wherever the value is finally used — often far
from, and long after, the boundary where the mistake was introduced.
Converting at the boundary (`ConvergenceStatus(raw_value)`, raising
immediately if `raw_value` is not a valid member) turns a silent,
distant failure into an immediate, loud one exactly where the bad
data entered.

`Enum` also solves a related but distinct problem: using `0`/`1` or
bare `bool` to represent a state that is not genuinely binary, or
that is binary today but grows a third state later (for
example, `is_running: bool` needing to become
"running/paused/stopped"). An `Enum` scales to a third state by
adding a member. A `bool` does not scale at all, and the two-state
assumption tends to leak into every comparison written against it.

## A note on `Literal` instead of `Enum`

`typing.Literal["running", "converged", "max_iters_reached"]` is the
obvious lighter alternative. It catches the same typo for a
value written directly in a type-checked source. A type checker flags
`Literal["convergd"]` immediately, matching `Enum`'s own
typo-catching claim above.

The difference appears once a type checker is not in the loop.
A `Literal` has no runtime existence of its own — it is a pure
annotation, erased once the interpreter runs. A value arriving from
JSON, a CSV row, an environment variable, or a database column is
typically `str`- or `Any`-typed at that boundary. A
`Literal`-annotated variable receiving it gets no actual check at
all, and the bad string flows straight through.

The rationale above depends on real runtime construction. A call
like `ConvergenceStatus(raw_value)` validates and raises
`ValueError` on a bad value, regardless of whether a type checker
ever ran over that code path. There exists no equivalent for `Literal`
— no object exists to build or validate against.

`Literal` remains a reasonable, lighter choice for a value that
never crosses an untyped boundary and never needs runtime
validation. A function parameter meant only for editor autocomplete,
and static checking is a good example. It is not a substitute for
`Enum` wherever a value might carry unchecked external input — the
exact scenario this rule cares about most.

Where the state also needs to interoperate with string-based
boundaries — serialized to JSON, written to a log, compared against
a raw value from outside the program — a plain `Enum` is not the
best fit. `enum.StrEnum`, standard library since Python 3.11
(pyrigor’s own floor version) is the better default there. It keeps
every runtime guarantee above while also behaving as a real string
at the boundary, removing the `.value` unwrapping a plain `Enum`
would otherwise require. Reserve a plain `Enum` for state that is
purely internal and never serialized.

## When this does not apply

- A value that is genuinely open-ended, not drawn from a fixed set
  (free-text input, a user-supplied name, a path).
- A boolean is truly, permanently binary and unlikely to grow a
  third state (for example, `is_empty: bool` on a container) — not
  every `bool` needs to become an `Enum`, only ones standing in for a
  closed set of *named states*, which a simple binary condition is not.
- Interop boundaries where a third-party API or file format mandates
  a specific string/int representation — the conversion to/from
  `Enum` still belongs at the boundary, but the wire format itself is
  not something this rule asks you to change.

## Related

- [PYR201](./PYR201-newtype-same-typed-values.md) — use `NewType` for
  same-typed values at risk of being swapped. PYR202 addresses a
  related but distinct failure: an unbounded type standing in for a
  closed set of states, rather than two same-typed values being
  confused with each other.

## Enforced by

Not yet implemented. Checked against existing tools first, per
`ADDING_A_RULE.md`’s step 0: `ruff` has no rule for this pattern.
`pylint`’s `magic-value-comparison` (R2004) is related but
broader — it flags any literal used in a comparison, whether a
numeric threshold or an arbitrary string, and suggests "a named
constant or an enum" generically. It does not distinguish a
continuous threshold from a genuinely closed set of named states,
so it does not specifically detect or enforce this rule’s narrower
claim. The gap PYR202 addresses remains real.
