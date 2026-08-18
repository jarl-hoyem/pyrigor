# PYR406 — Require every locally defined function’s non-`None` return value to be used.

## Rule

A function defined within the codebase being checked, whose return
type is not `None`, must have its return value used at every call
site. Calling it as a bare expression statement and discarding the
result is a violation.

```python
def compute_total(items: list[Item]) -> float:
    ...

# Bad
compute_total(items)

# Good
total = compute_total(items)
```

No decorator, no opt-in marker. This is structural, matching every
other enforced pyrigor rule. No developer has to remember to mark a
function before it is protected.

## Rationale

Calling a function purely for a side effect, and calling a function
to compute something you then discard, looks identical at the call
site, a bare expression statement. The difference is entirely in
intent, and intent is exactly what is easy to get wrong. A function
call meant to capture a result, `total = compute_total(items)`,
with the assignment dropped, still runs without error,
of any kind. The computed value is thrown away silently, and
whatever depended on it downstream either uses a stale or default
value or fails much later, far from the actual mistake.

```python
def validate_and_normalize(data: RawInput) -> NormalizedInput:
    ...

def handle_request(data: RawInput) -> None:
    validate_and_normalize(data)  # bug: result discarded
    process(data)  # still processing the raw, unvalidated input
```

This is precisely the class of bug MITRE’s CWE-252 (Unchecked
Return Value), and the equivalent SEI CERT rules for Java (EXP00-J)
and C (EXP12-C) describe. It is exactly what OSSF’s Secure
Coding Guide for Python, pyscg-0036 ("Check Return Values"),
addresses directly for Python specifically. This rule enforces that
guidance mechanically rather than relying on a reviewer noticing a
missing assignment by eye.

## Scope, deliberately narrow

A blanket version of this rule, flag every discarded non-`None`
return value anywhere, including calls into external libraries,
would be extremely noisy. Many library functions return a value by
convention that most callers legitimately never need (`dict.pop(key, None)`
used purely for its removal side effect, a builder method returning
`self` for optional chaining, a status code from a call whose
primary purpose is a side effect). Scoping this narrowly avoids that
noise entirely, rather than trying to detect every legitimate
exception automatically:

- **Only the functions defined within the codebase pyrigor is checking.**
  A call into an external library, anything not defined in the
  project’s own source, is never flagged, regardless of its return
  type. The project has no control over that library’s own
  conventions.
- **A function returning `None`** (explicit or inferred) is
  automatically excluded, there is nothing meaningful to discard.
  This removes the largest source of potential noise, `print`,
  `logger.info`, `list.append`, and any other side-effecting,
  `None`-returning function.
- **A function annotated `-> NoReturn` or `-> Never`** is
  automatically excluded. It never returns control to the caller at
  all, there is no return value to discard.
- **Bare-name calls** (`compute_total(items)`) are matched
  directly, and so is `self.<name>()`, narrowly: only when `<name>`
  is defined directly on the same class as the method making the
  call. A closure nested inside that method still counts, since its
  own `self` is the same instance. A nested class defined inside the
  method does not, since its own `self` refers to its own instance
  instead.
- **A subclass calling an inherited method through `self` is not
  detected.** Pyrigor never resolves a class hierarchy, only a
  class’s own directly defined methods. A `cls.<name>()` call is not
  detected either, out of scope for this narrower pass.
- **Any attribute call through something other than `self`**
  (`obj.compute_total()`) is never matched. Pyrigor cannot reliably
  determine which class or object an arbitrary attribute belongs to
  — it has no type inference, and processes one file at a time.
- **A `lambda` expression** is excluded entirely, structurally
  rather than as a deliberate carve-out. It has no `.name` for the
  checker’s name-matching mechanism to key on — only whatever
  variable it is assigned to carries a name. Python’s grammar also
  gives a `lambda` no `->` return-annotation slot at all, so even a
  named `lambda` could never satisfy the return-type check.

## When this does not apply

- A genuinely legitimate discard, a builder method returning `self`
  for optional chaining that is not being chained here, or a
  deliberate `dict.pop(key, None)`-style cleanup where the removed
  value is intentionally irrelevant. Use a suppression comment for
  these, `# pyrigor: 406 # deliberately discarding the removed value`,
  rather than expecting the rule to infer the exception
  automatically.
- Any call into code outside the project being checked. This rule
  never inspects or assumes anything about an external library’s own
  conventions.

## Not covered by this rule

A **generator function** (`-> Iterator[X]`, `Generator[X, Y, Z]`, or
`AsyncGenerator[X, Y]`), called and discarded, is a related but
distinct, arguably worse failure mode: discarding the call means
none of the function’s body ever runs at all, `yield` never executes
until something iterates the result, not merely "computed and
thrown away," but "never computed." This case is covered by PYR407
instead, a separate rule.

## Related

None yet.

## Enforced by

The `pyr406` checker (`pyrigor/checkers/pyr406_return_values_used.py`),
wired in as a pre-commit hook and available via the `pyrigor` CLI
(`pip install pyrigor`, then `pyrigor path/to/file.py`).
