# PYR404 — Use immutable default argument values, never mutable ones

## Rule

A function parameter’s default value must never be a mutable object
(`list`, `dict`, `set`, or any other mutable type). Use `None` as the
default and construct the mutable value inside the function body
instead.

```python
# Bad
def add_item(*, item: str, items: list[str] = []) -> list[str]:
    items.append(item)
    return items

# Good
def add_item(*, item: str, items: list[str] | None = None) -> list[str]:
    items = items if items is not None else []
    items.append(item)
    return items
```

## Rationale

A default argument value is evaluated exactly once, at the point the
function is defined, not once per call. For an immutable default
(`0`, `""`, `None`), this distinction never matters, since the value
cannot change regardless how many calls share it. For a mutable
default, every call that does not explicitly pass its own value
shares the same object, across every call, for the entire
lifetime of the function.

```python
def add_item(*, item: str, items: list[str] = []) -> list[str]:
    items.append(item)
    return items

first = add_item(item="a")
# first == ["a"], as expected

second = add_item(item="b")
# second == ["a", "b"] — not ["b"]. The same list object from the
# first call is still attached to the parameter's default, and the
# second call silently mutated it too.
```

This is not a hypothetical edge case. It reproduces every time a
function with a mutable default is called more than once without
explicitly overriding that parameter, and the resulting bug is
distant from its cause: the broken behavior shows up at the second
call site, or later, while the actual mistake is the function
definition itself, which can be far away and long since forgotten
about.

Using `None` as the default and constructing the mutable value
inside the function body closes this entirely. Every call that does
not pass its own value gets a fresh object, created fresh on that
specific call, never shared with any other call.

## When this does not apply

- The default value is genuinely meant to be the shared, persistent
  state across calls, and this is the deliberate design, such as a
  memoization cache keyed by call arguments. This is a narrow,
  unusual case, and should be accompanied by a comment making the
  intentional sharing explicit, since it looks identical to the bug
  this rule exists to prevent.
- The default is an immutable value (`int`, `float`, `str`, `bool`,
  `None`, a `tuple` of only immutable elements, a frozen
  `dataclass`), where the shared-object problem cannot occur at all.

## Related

- [PYR301](../PYR301-namedtuple-values.md) and
  [PYR405](../PYR405-namedtuple-parameters.md) — both address a
  different failure mode for parameter values (positional ambiguity
  in a bare tuple), not the shared-mutable-object problem this rule
  addresses. But worth reading together as part of the same general
  concern with parameter default and value safety.

## Enforced by

This rejected rule is covered by the guidance in [REJECTED.md](../REJECTED.md),
Ruff's `B006`, and Pylint's `W0102`.
