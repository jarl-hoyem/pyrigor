# Adding a new rule

A checklist for adding a new `PYRxxx` rule, covering both the
guideline doc and, if applicable, its checker. Written after this
project hit real, repeated friction from having no single place this
was written: a renumbering that required a full manual audit, a
file misnamed with the wrong rule number colliding with an already
reserved one, and a fully built, fully tested checker that sat
unregistered and never actually ran for several commits.

## 0. Check it is not already covered

Before writing anything, check whether ruff, pylint, or mypy strict
mode already catches the pattern. Pyrigor exists to fill gaps other
tools miss, not to re-implement checks they already do well. This
was skipped once already: PYR404 (mutable default arguments)
overlaps with the ruff's `B006` and pylint's `W0102`, discovered only
after the guideline doc was fully written.

If the pattern is already covered, do not write the rule. Add it to
[`REJECTED.md`](./REJECTED.md) instead, so the idea is not lost but
also is not rebuilt or re-debated later.

## 1. Pick a number

See [`NUMBERING.md`](./NUMBERING.md) for the bucket scheme. Check
`guidelines/` and open GitHub Issues for the current highest number in the
relevant bucket before claiming the next one.

## 2. Pick a name

See [`NAMING.md`](./NAMING.md). Name the mandated pattern, not what
is banned, unless the mandate-only name would be genuinely ambiguous
about what it replaces.

## 3. Write the guideline doc

File: `guidelines/PYRxxx-<symbolic-name>.md`. Follow the existing
structure: Rule, Rationale, When this does not apply, Related,
Enforced by. Cross-reference related rules in both directions, that
is update the other rule’s doc too, not just this one.

## 4. Register the rule

Add a member to the `Rule` enum in `pyrigor/rules.py`:

```python
from pyrigor.rules import Fixability, RuleInfo, Severity

PYRxxx = RuleInfo(
    symbolic_name="...",
    problem="...",
    severity=Severity.WARNING,  # ERROR | WARNING | INFO, see DECISIONS.md's "Severity" entry
    fixability=Fixability.GUIDANCE,  # SAFE_FIX | SUGGESTION | GUIDANCE
)
```

The filename slug from step 3 and `symbolic_name` here must match
exactly. This is checked automatically by
`tests/test_rules_docs_sync.py`, but it only catches the mismatch
after the fact, so get it right the first time.

Select `severity` and `fixability` deliberately from the guideline's
`Severity` and `Fix classification` sections. The `RuleInfo` is the
canonical source for implemented rules The documentation-sync test
must pass before the rule is considered complete.

## 5. If the rule is enforced, write the checker

- File: `pyrigor/checkers/pyrXXX_<symbolic-name>.py`.
- Signature: `find_violations(*, nodes: WalkedNodes) -> list[Violation]`.
  Do not call `ast.parse()` or walk the tree yourself inside the
  checker. Every checker receives the same pre-walked `WalkedNodes`
  (built once by `walk_once()` in `pyrigor/checkers/_shared.py`),
  shared across all registered checkers, so the tree is walked once
  per every file, not once per checker.
- Use `make_violation(node=node, rule=Rule.PYRxxx)` from
  `pyrigor/violations.py` to construct violations, rather than
  building `Violation` by hand.
- Check `pyrigor/checkers/_shared.py` for existing reusable logic
  before writing new AST-walking code. If the new checker needs
  logic that is a near-duplicate of an existing checker’s, extract
  it to `_shared.py` rather than copying it.

## 6. Write the checker’s tests

Test Driven Development (TDD): write a failing test before writing the checker.
Cover, at minimum, the following edge cases, since past checkers have hit real
bugs in every one of them:

- The straightforward violating case.
- The straightforward non-violating case.
- `self`/`cls` as a first parameter, if the rule concerns parameters.
- `async def`, not just `def` (`ast.AsyncFunctionDef` is a distinct
  node type from `ast.FunctionDef`).
- Nested functions and lambdas, and whether the rule should apply to
  each.
- Any parameter- or return-shape edge case specific to the rule
  (positional-only markers, `*args`/`**kwargs`, single-element
  tuples, ...).

## 7. Register the checker

Add the checker's `find_violations` to `CHECKERS` in
`pyrigor/checkers/__init__.py`:

```python
from pyrigor.checkers.pyrXXX_<symbolic_name> import find_violations as _pyrXXX

CHECKERS: tuple[RegisteredChecker, ...] = (
    RegisteredChecker(rule=Rule.PYR401, find_violations=_pyr401),
    RegisteredChecker(rule=Rule.PYR402, find_violations=_pyr402),
    RegisteredChecker(rule=Rule.PYRxxx, find_violations=_pyrXXX),
)
```

This step has been missed before. A fully built, fully tested
checker sat unregistered for several commits, invisible to the
actual `pyrigor` command and the pre-commit hook, because this step
was skipped. No automated check catches a
missing registration. Do this step deliberately, and confirm by
running `pyrigor` against a file that should trigger the new rule.

## 8. Mark the checker in the tach.toml

Mark the new checker file as its own module in `tach.toml`, isolated
from every other `pyrXXX` checker, the same as every existing one.
A checker not marked here falls outside `tach check`'s tracking
entirely, silently — the same class of gap `CHECKERS` registration
already warns about above. Run `tach check` to confirm.

## 9. Update the README

Add a row to the guideline table in `README.md`, in numeric order,
with the correct "Enforced by" value.

## 10. Add a pre-commit hook, if enforced

Confirm the hook in `.pre-commit-config.yaml` still says "runs every
registered checker" accurately. If checkers are ever split into
separate hooks again, add a new hook entry here.

## 11. Run the full suite

`pre-commit run --all-files`. All checks are green, 100 percent coverage,
before committing.
