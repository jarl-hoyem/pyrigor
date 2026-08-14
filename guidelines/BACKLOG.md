# MISRA-Style Rigor in Python — Habits to Build Over Time

Reference notes from the ML course sessions. Not urgent — revisit and adopt gradually.

## 1. Never use direct float equality

_Written up as PYR204._

```python
# Bad
converging = (cost - new_cost) == 0

# Good
converging = abs(cost - new_cost) < 1e-12
```

Floats rarely land exactly on a value due to rounding. This is a real latent bug pattern, not just style.

## 2. `Final` for values that should never be reassigned

_Written up as PYR203._

```python
from typing import Final

LEARNING_RATE: Final = 0.001
```

The mypy errors, if anything, later tries to rebind it.

## 3. Frozen structures for all multi-field states

_Written up as PYR302._

Use `NamedTuple` or `@dataclass(frozen=True)` for any structured data passed around — not just function returns. Nothing
should be mutable after construction unless it needs to be.

## 4. `Enum` instead of magic strings/bools for state

_Written up as PYR202._

```python
from enum import Enum, auto

class ConvergenceStatus(Enum):
    RUNNING = auto()
    CONVERGED = auto()
    MAX_ITERS_REACHED = auto()
```

Prevents typos like `"convergd"` from doing nothing silently. The tool mypy catches invalid members.

## 5. Keep mypy `--strict`, resist `Any` leaking in

Already in use — every `no-any-return` error caught by this discipline confirms it is working.
## 6. Never use mutable default arguments

_Written up as PYR404._

```python
# Bad — shared mutable state across every call
def f(items: list = []):
    ...

# Good
def f(items: list | None = None):
    items = items if items is not None else []
```

## 7. `assert_never` for exhaustiveness checking

_Written up as PYR501._

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

_Written up as PYR502._

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
confusion is not realistically possible.

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
when the mislabeled variable is later used in a way that exposes its true type. For example, calling '.tolist()' on
what you thought was a float, a runtime crash, not a caught error.
NamedTuple field access removes the positional slot entirely, so there is nothing to mislabel.

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

## Future tooling ideas

### Suppression audit report

`filter_suppressed` already parses an optional free-text reason from
`# pyrigor: CODE # reason` comments (captured, not yet surfaced
anywhere). A natural follow-on: a report command walks a
codebase, collects every active suppression comment and its reason,
and outputs a summary — useful for a team lead reviewing what is being
silenced and why, the same way an old, unreviewed `# noqa` comment
tends to accumulate unexamined on larger codebases.

Not yet designed. Would likely need its own CLI subcommand (separate
from the per-checker `main()` entry points) and its own output
format — deliberately out of scope for the initial suppression
mechanism itself.

### Per-rule violation counts, and a full summary report

The current summary line reports a single total violation count.
Worth extending into a proper breakdown — for example, the "PYR401: 12
violations, PYR402: 64 violations" — and eventually a fuller report
(most-violated files, the most common rule, trend over time if run
repeatedly). Natural pairing with the suppression audit report idea
above. Both are "summarize what pyrigor found/did across a run"
features and might share infrastructure or even a CLI flag
(`--report`) once designed together.

### Structured argument parsing

The CLI parses flags manually (`"--version" in sys.argv`),
fine for a single flag. Once a second or third flag exists (per-rule
excludes and a `--report` flag are both already noted above), this
should move to `argparse` (the standard library, no new dependency)
rather than continuing to hand-check `sys.argv` for each new flag.
Not urgent with only one flag today.

### Proper `.gitignore`-aware file discovery

`_collect_python_files()` currently uses a small hardcoded exclude
list (`.venv`, `.git`, `__pycache__`, `node_modules`, ...) when
walking directories, rather than respecting the repo’s actual
`.gitignore`. Good enough for now — the goal was avoiding wasted
time/noise on vendored or generated code, not building a general
file-discovery engine. Worth revisiting if the hardcoded list proves
not enough in practice (a real project with unusual excludes not on
the default list), or once there is a concrete reason to match `git
ls-files`/`.gitignore` semantics exactly.

### Per-rule directory/file excludes

Right now, excluding a path from pyrigor entirely means excluding it
at the pre-commit level (`exclude: ^tests/` in
`.pre-commit-config.yaml`) — all-or-nothing across every rule. A more
precise mechanism would let a project exclude specific rules from
specific paths (for example, "PYR402 does not apply under `tests/`, but PYR401
still does"), like ruff's `per-file-ignores`. Not yet designed. Would likely
live in a project-level pyrigor config file (`pyproject.toml` section,
or a dedicated config file), which does not exist yet.

### Detect unnecessary suppression comments

The tool mypy (and other type checkers) can flag a `# type: ignore` that’s no
longer suppressing anything, because the underlying issue was fixed,
and the suppression became dead weight. The tool pyrigor’s suppression comments
have the same problem: a `# pyrigor: CODE # reason` sitting on a line
that no longer actually violates that rule (because the code changed,
or the rule’s logic changed) is not flagged as unnecessary —
it just silently does nothing forever. Worth detecting and warning on
stale/unnecessary suppressions, the same way `filter_suppressed`
already warns on malformed or missing-reason ones.

### `--version` flag

The `pyrigor` CLI has no way to report its own installed version —
found while trying to confirm, which pyrigor version was installed in
a separate downstream project (`uv pip show pyrigor` was the
workaround). Small, standard, and genuinely useful once pyrigor is
used across multiple projects. Should be quick to add whenever
picked up — likely just a `--version`/`-V` flag in `run()` that reads
the installed package’s own version and exits, without needing to
touch `main()`'s actual checking logic.

### Changelog draft generator

`publish.yaml` could write the real release date into `CHANGELOG.md`
automatically, reading `github.event.release.published_at` and
replacing the matching version heading's `TODO`. Small, mechanical,
worth doing whenever picked up.

Generating the actual content is a different, harder problem, not
worth doing the same way. A tool that dumps every commit message
since the last tag tends to produce a noisy, unhelpful changelog,
especially given this project’s own commit messages are often long
and detailed for their own sake, not written as changelog-ready
one-liners. A better middle ground: since commit messages already
follow Conventional Commits (enforced by the `commitizen` hook), a
script could group commits by type (`feat`, `fix`, `docs`, `chore`)
since the last tag and generate a draft `CHANGELOG.md` section,
reviewed and trimmed by hand before a release rather than written
from scratch. Real, buildable, but a genuinely new tool, not a small
addition.
