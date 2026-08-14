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

## 11. Disallow ignoring a return value marked as required

_Reserved as PYR406. Not yet written up._

Like C++'s `[[nodiscard]]` or Rust's `#[must_use]`. A function’s
return value being silently discarded, called as a bare statement,
is very likely a bug if that return value is meaningful, `x = f()`
intended, `f()` written by mistake. Cannot be detected by inference
alone, same lesson as PYR203’s original mistake. Most discarded
return values are entirely intentional (`print(...)`, `logging.info(...)`,
`list.append(...)`). Needs an explicit marker the developer applies,
a decorator most likely, then a mechanical check that a decorated
function is never called as a bare expression statement.

Worth checking overlap before writing the full doc, not confidently
verified whether ruff or pylint already cover this pattern.

## 12. Suppression counts per rule in the summary

Half-designed, not yet applied. The function filter_suppressed(violations, source)
returns only the kept violations, silently discarding that
ones were suppressed and under which rule. To add "PYR402: 3
suppressed" to the summary alongside the existing per-rule and
per-file violation counts, filter suppressed needs to return both
lists, likely a SuppressionResult(kept, suppressed) NamedTuple rather
than a bare list. This is a real, breaking change to
filter suppressed’s return type, every existing caller and test
needs updating, not just cli.py.

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

### Run mutmut locally on pre-push, not just CI

The tool mutmut only run, when it runs at all, as a manual or CI
step. Worth adding as a pre-push hook (not pre-commit, too slow for
every commit) so mutation-testing feedback happens locally before
pushing, not only after.

### Review tool exemptions carried over from Pickomino

Several tool-level exemptions, exclusions, or ignored rules in,
`.pre-commit-config.yaml` and `pyproject.toml` were copied directly
from Pickomino’s own config as a starting template, not re-evaluated
for whether they actually apply to pyrigor. Worth a deliberate pass
checking each one against pyrigor’s own codebase and needs, rather
than carrying Pickomino-specific exceptions forward by default.

### A Rust implementation for a single file or module

Explicitly a learning exercise, not a performance need (see
`PERFORMANCE.md`'s own reasoning for why a full Rust rewrite is not
justified now). Worth trying on one small,
self-contained
module first, to learn the shape of a Python/Rust boundary (`PyO3`
or similar) before considering anything larger.

### Rule: No variable names without vowels

A readability rule, `wrd` or `cnt` where `word` or `count` would be
clear. Needs a real design decision on scope and exceptions
(genuine abbreviations, loop indexes) before it could avoid being
noisy the way an early, unscoped magic-number rule would have been.

### Rule: No variable names under four characters, with exceptions

In the same category as the vowel rule, a readability constraint, not a
correctness one. Needs the exception list worked out carefully,
loop counters (`i`, `j`), coordinates (`x`, `y`), and common,
well-understood short names would need explicit carve-outs, or this
would be noisy on real code.

### Adoption guide split: New project versus legacy codebase

The current README and CONTRIBUTING content assumes a reader
starting fresh. A real legacy codebase adopting pyrigor for the
first time has a very different experience, hundreds or thousands
of pre-existing violations, likely needing a gradual, per-rule
rollout strategy. Adopt one rule, fix it, add the next rather than
turning on all rules at once. Worth a dedicated adoption guide
covering both paths.

### A pyrigor badge, like ruff's own

Ruff has a shields.io-style badge projects can add to their own
README, signaling "checked with ruff." Worth building the same for
pyrigor, once there is a real audience of adopting projects for it
to matter to.

### Distinguish "unadopted convention" rules from "avoidable footgun" rules in reporting

Found while running pyrigor against mypy’s own codebase: PYR402 and
PYR403 fired thousands of times, high counts that mostly reflect a
community-wide convention (bare `*` for keyword-only arguments)
essentially no pre-existing codebase has adopted, not carelessness.
PYR301, PYR401, and PYR405 fired far less (3, 225, and 24 respectively
across 441 files), a more genuinely meaningful signal, since these
catch a specific, well-known, avoidable bug (positionally ambiguous
multi-value data) rather than an unadopted stylistic choice.

A low count in the second category is real evidence of deliberate
discipline. A low count on the first category mostly is not. Worth
surfacing this distinction in future reporting, PERFORMANCE.md, a
future `--report` output, or documentation, rather than presenting
every rule’s violation count with equal weight, which invites
exactly the kind of misread a raw total would otherwise cause.

### CLI flag to filter, which rules run: `--only`

Design worked out, not yet applied. `pyrigor --only PYR301,PYR401
path` should run and report only the specified rules, filtering
`CHECKERS` before the checker loop, rather than running everything
and discarding unwanted output. Multiple rules comma-separated, one
flag, matching the suppression comment’s own convention. Should
accept the same lenient forms suppression comments already do, full
code, bare number, or symbolic name, not just the full `PYRxxx` form.

Found genuinely useful while comparing pyrigor’s own findings
against real public style guides (Google’s Python Style Guide in
particular), wanting to isolate one rule’s results against a large
repo without the other four rules’ output in the way.

Needs `main()` itself to accept an optional filter set, not just
`run()` parsing argv, since `main()` is what actually knows about
`CHECKERS`. First test drafted:

```python
def test_main_only_runs_specified_rule(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """With only={"PYR401"}, only PYR401 violations should be reported, even if others exist."""
    (tmp_path / "bad.py").write_text(
        "def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n"
    )

    main(paths=[str(tmp_path)], only={"PYR401"})

    captured = capsys.readouterr()
    assert "PYR401" in captured.out
    assert "PYR402" not in captured.out
```

### PYR406 (return-value-must-be-used) has a real precedent

OSSF’s Secure Coding Guide for Python, pyscg-0036 ("Check Return
Values"), is a direct, independent match for the reserved PYR406
idea (disallow ignoring a return value marked as required). Cites
MITRE CWE-252 (Unchecked Return Value) and equivalent SEI CERT rules
for Java (EXP00-J) and C (EXP12-C). Worth citing directly when
PYR406’s full guideline doc is eventually written, real, credible,
independent corroboration, not just an analogy to C++/Rust.

### OSSF Secure Coding Guide for Python, a broader review worth doing.

https://github.com/ossf/wg-best-practices-os-developers/tree/main/docs/Secure-Coding-Guide-for-Python
A real, structured, numbered guideline set (pyscg-NNNN), similar in
spirit to pyrigor’s own PYRxxx documents, compliant/noncompliant
example code per rule. Only three of its ~15+ guidelines were
checked today (numbers section, coding-standards section). Worth a
fuller pass across all ten sections (encoding, neutralization,
exception handling, logging, concurrency, cryptography included) for
further overlap or corroboration, given how directly relevant the
three checked so far turned out to be.

### Rule: `not x` / truthiness check a NamedTuple or dataclass is almost always wrong.

Found live today: `filter_suppressed`'s return type changed from a
bare `list[Violation]` to `SuppressionResult(kept, suppressed)`, a
`NamedTuple`. Every existing `assert not result` silently kept
compiling and kept meaning something, just the wrong thing — a
2-element `NamedTuple` is never falsy regardless of its contents, so
`not result` always evaluates `False`, always failing, but for a
completely different reason than the test intended to check.

This is a real, checkable pattern: `not x` or `if x:` on a value
statically known to be a `NamedTuple` or `dataclass` instance (not a
`bool`, not a container) is seldom the actual intent, since
these types do not override truthiness and default to always-truthy.
Structurally like to PYR301/401/405’s own concern — a refactor
silently changes behavior with no error —, but the trigger here is a
truthiness check against a structured type, not a bare tuple
annotation. Not yet numbered or scoped. Needs its own design pass on
how to detect "this name is bound to a NamedTuple/dataclass instance"
reliably via AST alone before it is tractable to build.

### Auto fix for PYR402/PYR403

The only rules where auto fix is genuinely tractable: inserting `*,`
before the first parameter is fully mechanical, no judgment involved
in what the fix is. Every other current rule (PYR301/401/405, needs
invented names for a new NamedTuple and its fields. PYR203/205, needs
a meaningful constant name) requires real judgment a tool cannot
supply, and auto generating placeholder names would produce worse
code than the violation it replaced.

Real complication even for PYR402/PYR403: changing a signature this
way breaks every existing positional caller, unlike a formatter’s
fix, which is behavior-preserving by construction. Needs a design
decision: rewrite every call site to the keyword form too (much more
invasive, closer to a real refactoring tool than a linter), or only
fix the signature and let resulting TypeErrors at call sites surface
the remaining work. Given the earlier documented caution about
`ruff --fix` "messing everything up," worth treating any auto fix
here as opt-in and clearly scoped, not a default behavior.
