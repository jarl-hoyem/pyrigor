# Design and architecture decisions

A running log of *why* a structural choice was made, not just the
result. Read this before asking "why does the code do it this way"
rather than re-deriving the reasoning from scratch.

## Testing and release confidence

### Adversarial test matrices and installed-artifact checks are complementary

The PYR406 torture-test pass found real defects in lexical binding:
later lambda and import rebinding, comprehension-local targets and
class-body bindings all produced incorrect results until tested as
deliberate combinations. The lesson is broader than PYR406: test the
behavior an adversarial reader would try to break, not only the happy
path or the line that motivated the change.

The same pass also verified the built wheel and source distribution in
isolated environments. The editable checkout had already passed, but
that could not prove the release artifacts contained the right modules
and entry point. The source-level matrices and installed-artifact
smoke tests are separate confidence layers. Neither replaces the other.

## pyrigor architecture and rules

### NamedTuple and NewType close different gaps

NamedTuple for returns, NewType for same-typed values at risk of confusion.

Rule:

Always use NamedTuple for any function returning more than one
value. This removes positional-unpacking ambiguity. The caller
accesses fields by name (result.dj_dw), not position, so a
mislabeled variable at the call site can no longer silently receive
the wrong value.

Use NewType for any same-typed values, whether function arguments or
NamedTuple fields, that could plausibly be swapped or confused (for
example, Weight/Bias when both might be represented as float or a
same-shaped ndarray). Skip it where confusion is not realistically
possible.

Why:

Different-typed arguments (for example, w: np.ndarray, b: float) are
already protected by mypy, a swap at the call site is a type
mismatch and gets caught. No NewType needed here.

Same-typed arguments (for example, two float parameters) are not
protected by mypy alone. Both are structurally identical, so a swap
is a silent, valid-looking call. NewType makes them nominally
distinct, so mypy catches the swap.

NamedTuple closes a separate gap: even with a fully typed
multi-value return (for example, tuple[np.ndarray, float]), mypy
checks the type at each position but not the name the caller gives it.
A caller can unpack into misleadingly named variables
(dj_db_temp, dj_dw_temp = ... when the function actually returns
dj_dw, dj_db), and mypy will not catch it, because the types still
line up positionally, only the semantics are wrong. This is a silent
bug that surfaces only when the mislabeled variable is later used in
a way that exposes its true type. For example, calling '.tolist()' on
an assumed float, a runtime crash, not a caught error.

NamedTuple field access removes the positional slot entirely, so
there is nothing to mislabel.

Combined, these two will catch:

- Argument-order swaps for differently typed args: plain type
  annotations (no extra tooling needed).
- Argument-order swaps for same-typed args: NewType.
- Return-unpacking mislabeling for differently typed return values:
  NamedTuple alone.
- Return-unpacking mislabeling for same-typed return fields:
  NamedTuple and NewType together.

Example:

```python
class GradientResult(NamedTuple):
    dj_dw: Weight
    dj_db: Bias


def compute_gradient_logistic(x: np.ndarray, y: np.ndarray, w: Weight, b: Bias) -> GradientResult:
    ...
    return GradientResult(dj_dw=dj_dw, dj_db=dj_db)
```

### Shared AST walk instead of per-checker walking, and why a cache was rejected

Every checker originally called `ast.walk(tree)` independently, once
per checker per the file. Profiling against the Home Assistant core
(18,187 files) found this was the dominant cost: `ast.walk` itself
accounted for 286 of 388 seconds, and the cost scaled linearly with
the number of registered checkers, every future rule added would
make it worse.

Two designs were considered.

**Cache-based** (rejected): keep every checker’s own
`find_violations(*, tree)` signature exactly as-is, walk once inside
`_run_checkers`, and cache the result keyed by `id(tree)`, so a
repeated internal `ast.walk` call inside `_shared.py` would hit the
cache rather than re-walking. Smaller diff, no signature changes
anywhere. Rejected because it is exactly the kind of implicit,
hidden coupling this project has repeatedly been burned by — the
`zip(CHECKERS, Rule)` positional-coupling bug fixed earlier is the
same category of problems. It rests on an unenforced assumption:
"every checker always walks the same cached tree." It also does not
remove the actual walk cost — it only hides one walk behind a
cache lookup. Real savings would require every future checker’s own
logic to want the tree walked in the same way, silently broken
the moment one does not.

**Nodes-based** (chosen): walk the tree exactly once in
`_run_checkers`, via `walk_once()`, producing a `WalkedNodes(
function_nodes, assign_nodes)`. Every checker’s own public
`find_violations` signature changes from `(*, tree: ast.Module)` to
`(*, nodes: WalkedNodes)`, an honest interface describing exactly
what each checker actually needs, rather than "a tree, which happens
to be pre-walked somewhere else by convention." Real cost: touched
five checker files, the `_CheckerFun` Protocol, and every existing
test calling `find_violations` directly. Real result: confirmed via
profiling, `ast.walk`'s own call count dropped exactly 5.0x
(69,393,100 to 13,878,620), and real-world timing on the same
18,187-file run dropped from 388.20 s to 55.46 s, 7x.

### PYR406 matches only bare-name calls, not attribute calls

PYR406 flags a discarded call only when the callee is a bare name
(`compute_total(items)`), never through attribute access
(`self.compute_total()`, `obj.compute_total()`). Consequently,
functions with a leading `self`/`cls` parameter (methods) are
excluded from the protected set entirely.

Why: pyrigor cannot reliably determine which class or object an
attribute call belongs to — it has no type inference and
processes one file at a time. Without this exclusion, matching
by name alone would let a method’s name enter the protected set
even though nothing ever calls it as a bare name. The only effect would be
a false positive on some unrelated bare call elsewhere in the file
that happens to share the method’s name. Excluding likely methods
removes that risk at the cost of not covering method calls at all,
consistent with the guideline doc’s own examples, which are all
bare-name, module level or nested function calls.

The lexical-scope utilities used to resolve those bare names live in
`checkers/_shared.py`, rather than in PYR406. This is deliberate: the
documented PYR407 generator-result rule has the same local-definition
and bare-call boundaries and is the planned second consumer. The
shared layer provides scope structure. Each rule retains its own
return-value classification.

### The --select/--ignore combines like ruff’s select/ignore, and full-overlap combination errors

`--only` was renamed to `--select` (#68), and `--ignore` was added
(#69) as its rule-axis opposite, matching ruff’s own `select`/
`ignore` pair rather than inventing pyrigor-specific terms (a
principle first stated on #66).

Combination semantics, verified against ruff’s own documented
behavior rather than assumed: `--ignore` removes codes from
`--select`’s set (or from every rule, if `--select` is omitted).
Order on the command line never matters. Argparse collects each
flag’s own value independently of where it sits relative to the
other flag. `_filter_checkers()`’s combination logic is pure set
arithmetic on the final parsed values, not a fold over argv in parse
order. Partial overlap (`--select=PYR401,PYR402 --ignore=PYR402`,
leaving PYR401) is the intended, normal use case, matching ruff’s
own documented "select a category, ignore one rule within it"
pattern — not an error.

Full overlap is different in kind, not just degree — a combination
that empties the selection entirely (`--select 403 --ignore 403`)
produces zero checkers to run. That is technically successful but
certainly unintended, the same failure shape `nargs="+"` already
closed for zero paths (#51). The `_reject_empty_selection()` catches
this in `run()`, not inside `main()`, keeping `main()` a pure
function that never touches `sys.exit()`/stderr itself. This costs
one extra, inexpensive call to `_filter_checkers()` (pure, iterating a
small fixed tuple) but preserves that separation rather than
threading exit-code concerns into the library function tests call
directly.

### CLI exit code 2 covers both a crash and a bad invocation, deliberately not split

When pyrigor's `run()` migrated from hand-rolled `sys.argv` scanning
to `argparse` (#51), argparse’s own native parse errors (unrecognized
flag, missing required `paths`) landed on exit code 2 — the same code
already used for two different pre-existing cases: an unexpected
internal crash (the top-level `except Exception` handler) and a bad
`--only` invocation (repeated flag, unknown rule code). All three
now share one exit code.

Decided not to split them. Reasoning: the ambiguity predates this
migration — "2 means either a crash or a bad invocation" was already
the convention before argparse was introduced, so widening it to
argparse’s own errors is consistent, not a new compromise. Splitting
would need either a custom `ArgumentParser` subclass overriding
`error()`, or wrapping `parse_args()` in `try/except SystemExit` to
remap its code — real added surface area for a distinction no test,
issue or actual consumer of pyrigor’s exit code has needed yet. If
a concrete need for the distinction shows up later (for example, a
CI wrapper that retries on exit 2 assuming it is transient, when a bad
invocation is not). That is the evidence to revisit this, not a
preference alone.

## Fix classification: Adopt now, architecture: Defer

Considered whether current rule-building should expect a future
FixProposal architecture (detect()/suggest(), a three-tier fix
classification: safe_fix/suggestion/guidance, full CLI→editor
extension→Language Server Protocol (LSP) roadmap), per a real, external strategy document
(#105).

Split the decision cleanly. Documenting a real fix classification
per rule costs nothing, no code changes and already proved
valuable once: working through it caught a real, initial
misclassification (PYR402/PYR403 first looked unsafe due to caller
breakage, corrected once the actual, primary scenario, editor-time
feedback on a function with no callers yet was considered). Adopted as a permanent, standing part of every new rule
doc's own template.

The actual FixProposal architecture itself (a real suggest()
implementation, editor extensions, an LSP) is explicitly deferred,
not adopted now. Building real engineering toward editor integration
for a tool with zero real external adopters and no editor
integration at all yet is exactly the kind of premature investment
already identified as this project's biggest real risk. Revisit only
once real, concrete demand exists, a real user asking, or genuine
editor-integration work actually starting, not before.

## Severity: Language Server Protocol DiagnosticSeverity naming adopted, real per-rule levels assigned

A real `severity` field is used by the `--output-format=json`
diagnostic schema (file, line/column, rule ID, message,
severity, per `pyrigor_strategy.txt`'s own Stage 1 requirements), and
nothing in pyrigor's own `Rule`/`RuleInfo` structure provided one
until now (#158).

Scheme: reused the Language Server Protocol's own `DiagnosticSeverity`
naming (`Error`, `Warning`, `Information`, `Hint`) rather than
inventing pyrigor-specific terms, matching the same "match an
existing tool's own naming, do not invent" principle already applied
to `--select`/`--ignore` (#66). Chosen specifically because pyrigor's
own roadmap already commits to eventual LSP integration (#152,
deferred but decided) — assigning severities in LSP's own vocabulary
now means zero translation layer once that work actually starts. Used
three of LSP's four levels (`error`/`warning`/`info`, the common short
form of `Information`) — `Hint` was not used, since none of pyrigor's
18 rules are pure editor-hint-level suggestions. Even the
lightest-weight ones are real, considered diagnostics.

Graded by consequence severity if the underlying pattern's bug
actually occurs, not by how likely that is — a rule catching a rare
but catastrophic bug outranks one catching a common but low-stakes
one.

| Rule(s)              | Severity | Why                                                                      |
|----------------------|----------|--------------------------------------------------------------------------|
| PYR503               | error    | A real, confirmed vulnerability class (Zip Slip), not just style         |
| PYR303               | error    | Silently skips elements, real silent data loss, no exception raised      |
| PYR501               | error    | A newly added case silently falls through as a no-op                     |
| PYR204               | error    | Float-equality bugs are a classic, well-documented failure class         |
| PYR206               | error    | Silently constructs a different value than the one written               |
| PYR406/PYR407        | error    | A computed value is discarded, or a generator body never executes at all |
| PYR301/PYR401/PYR405 | warning  | Real swap-risk protection, narrower blast radius than error-tier         |
| PYR402/PYR403        | warning  | Defense-in-depth; caller consequence already loud via mypy/pyright       |
| PYR201               | warning  | Prevents same-typed-value confusion, requires the swap to occur          |
| PYR202               | warning  | Prevents typo-driven failures, not yet seen misbehaving in practice      |
| PYR302               | warning  | Prevents accidental mutation, narrower blast radius than error-tier      |
| PYR502               | warning  | Turns a distant, confusing failure into an immediate, clear one          |
| PYR203/PYR205        | info     | Readability and drift prevention, not a silent-wrong-output risk         |

Wired into `pyrigor/rules.py` for the six built rules (a `Severity`
enum, not a bare string — using one here would contradict PYR202's
own point while implementing severity for it). The twelve
documented-but-unbuilt rules carry their severity in their own
guideline doc only, until each is actually built, following
`ADDING_A_RULE.md`'s checklist.

### JSON diagnostics are a versioned contract, not a serialization detail

The `--output-format=json` output is an editor and tooling API. Its
published JSON Schema is therefore part of the API: contract tests must
validate actual output for clean results, diagnostics, suppression and
operational errors. Rule metadata such as severity and fixability has one
canonical source in `RuleInfo`. Documentation and tests should detect drift
rather than duplicate the classification independently. Human output remains
a separate compatibility surface. Source locations expose Python text
columns (code points), not encoded byte offsets, and Unicode behavior is
covered explicitly.

## Opt-in rule tier: Real, two independent axes, no separate numbering

Found while considering a "ban the walrus operator" rule (#163): every
PYRxxx rule today is framed as eventually default-enforced, catching a
silent bug type checkers/standard linters miss. A walrus-ban does not
fit that framing — it is a genuine readability preference, not a
silent-bug detector, but still a real, structurally checkable rule
someone might deliberately want (#162).

**Decision: yes, pyrigor supports a distinct, explicitly opt-in rule
tier.** Real, concrete demand already exists (#163), and MISRA — the
project's own repeatedly cited inspiration — already distinguishes
Mandatory/Required/Advisory rules rather than treating an opinionated
rule as beneath inclusion.

**No separate numbering namespace, unlike `PYREJECT1xx`.** First
proposed a `PYROPT1xx` prefix, mirroring the rejected-rules namespace.
Rejected: `PYREJECT1xx` is safe specifically because rejection is
permanent — nothing ever moves out of that bucket. An opt-in rule's
tier is not permanent in the same way: a rule might start opt-in and
later prove popular enough to go default, or the reverse. Baking tier
into the number would mean renumbering on any such move, breaking
every existing suppression comment and `--select`/`--ignore`
reference written against the old number — exactly the unstable-identity problem this project has already been burned
by (the
`zip(CHECKERS, Rule)` positional-coupling bug. The "rule identity flows
from one place"). Opt-in rules get a normal `PYRxxx` number from
`NUMBERING.md`'s existing bucket scheme, same as any other rule.

Verified this against a real precedent rather than assuming: MISRA C
itself keeps rule numbers fixed and has a formal Guideline
Re-categorization Plan (GRP) specifically for moving a rule between
Mandatory/Required/Advisory without renumbering it — confirming
number-stable, metadata-changeable is the established pattern for
exactly this problem, not an invented workaround.

**Two independent metadata axes on `RuleInfo`, not one:**

- **`Tier`: `Default` | `Advisory`** (MISRA naming). Controls real CLI
  behavior: `Default` rules run without being selected, matching
  every rule today. `Advisory` rules are excluded from that implicit
  default set — reachable only via explicit `--select=PYRxxx` (or
  symbolic name), never by omitting `--select` (which means "run the
  default set") and never via `--ignore` alone (which only removes
  codes from an already-selected set. An `Advisory` rule was never in
  that starting set).
- **`Maturity`: `Stable` | `Preview`** (Ruff naming, checked against
  Ruff's own docs rather than assumed). A genuinely different axis
  from `Tier` — how proven a rule is, independent of whether it is
  meant to be universal or opinionated. All six built rules
  are retroactively `Stable`, already proven through this project's
  own dogfooding history. `Preview` is documentation-only for now, no
  CLI flag of its own — it does not gate whether a rule runs. `Tier`
  alone does that. Not adding Ruff's `Deprecated`/
  `Removed` states or a `--preview` CLI switch: no rule has ever
  needed either, and building them speculatively would repeat the
  premature-investment mistake the FixProposal deferral above already
  identified. Add them later if real demand shows up, not now.

## Development process and tooling

### Fixer interface: explicit selection, in-place fix, diff preview

The first fixer is exposed through `--fix --select PYR402`, with `--diff`
providing a non-writing unified-diff preview. Both `--option value` and
`--option=value` forms are accepted because they are equivalent argparse
interfaces users reasonably expect.

Fixer modes require explicit PYR402 selection. Unlike a general-purpose
linter that may fix every rule marked safe, pyrigor's PYR402 transformation
can make existing positional calls fail at runtime. Requiring the rule in
the command makes that behavior deliberate and auditable. Rejected or
unsupported source is reported and left unchanged; the fixer never inserts
automatic suppressions. Source bytes, UTF-8 BOMs and line endings are
preserved wherever the source can be decoded as UTF-8.

### Fixer encoding boundary: reject non-UTF-8 sources

The PYR402 fixer explicitly rejects source files that cannot be decoded
as UTF-8, including other declared source encodings. Python 3.11+
support does not make arbitrary source encodings safe on the round-trip:
encoding detection, rewriting and byte preservation would each need
separate guarantees. Leaving an unsupported file unchanged is safer than
risking corruption. Broader source-encoding support is deferred to a
separate design decision.

### Tool findings: Fix, then suppress narrow before broad

Real, six-step order, not "fix or ignore": **fix → line suppress →
function suppress → file suppress → folder suppress → project
exclude.** Each step moves down this list only once the narrower
option genuinely does not fit — never skipped to for convenience.

Why the order matters: each step hides more code from a tool's own
scrutiny than the last. Line suppression affects one line. A
function-level exemption (complexipy's own `# complexipy: ignore`)
still leaves the rest of that file checked. A file-level exemption
(xenon-shared, scoped to `_shared.py` by name) means nothing in that
one file is checked by that tool again — but everything else still
is checked. A folder-level exemption (ruff's own `per-file-ignores`:
`"tests/**"` for `S101`/`PLR2004`, since `assert` is pytest's own
idiom and a literal comparison is the test's own job, not a magic
value. The `"scripts/**"` for `T201`, since `print` is a standalone
script's real output) is broader still, exempting every file a whole
directory ever contains, present or future — a real, deliberate
reason at the directory's own scope, not one file's. A project-wide
exclude (`markdownlint`'s `MD018` disabled outright) means no file
anywhere, ever, is checked for that pattern — the largest, most
permanent blind spot a tool-finding response can create, reserved
for when the finding itself is wrong for the project, not just
wrong in one spot.

This was not decided in the abstract — it is the pattern this project's
own real decisions already follow, named explicitly here for the
first time rather than left implicit. Each level above has a real,
already-adopted precedent, not a hypothetical one.

### GitHub Issues are referenced as a bare `#N`, never a linked title

Now that `BACKLOG.md` is retired and every real work item lives as a
GitHub Issue, `DECISIONS.md` and `REVIEW_CHECKLIST.md` needed a
single, deliberate convention for referencing one, rather than an
adhoc choice made differently each time (#101).

Checked the actual, current practice across both files first, rather
than picking a convention in the abstract: every existing reference
in `DECISIONS.md` already uses a bare `#N` (`(#68)`, `on #66`,
`#19 added...`, `#56 (move to an org...) still stands`), sometimes
with a short inline parenthetical gloss when the number alone would
not orient an unfamiliar reader, sometimes without. The file `REVIEW_CHECKLIST.md`
has no issue-number references at all.

Chosen: keep the already-consistent bare `#N` form, with an optional
short parenthetical gloss at the author's own discretion for a
number a reader is unlikely to recognize on sight. Not a linked
Markdown title — GitHub already auto-links a bare `#N` inline within
its own rendering, so a manual `[title](url)` link would be
a redundant markup for zero real benefit, and would also silently go
stale if the issue's title is ever edited later.

No retrofit needed: every existing reference in both files already
matches this convention.

### The tool complexipy runs through a Python wrapper, not a .bat script

The tool complexipy’s own console output (via `rich`) crashes on Windows’
legacy `cp1252` codepage when printing status emoji, confirmed
across two different pinned versions (an octopus at v3.0.0, a
checkmark at v7.0.1), a genuine, systemic upstream bug, not fixed
between releases.

A Windows batch script (`scripts/run_complexipy.bat` setting
`PYTHONUTF8=1` before invoking the binary) was considered first, and
would have worked locally. Rejected because it is Windows-only,
`.bat` syntax and `%*` argument forwarding mean nothing on macOS or
Linux, and this project’s own CI matrix explicitly tests
`ubuntu-latest`, `macos-latest`, and `windows-latest`. A fix that
only works for one contributor’s own OS is not a real fix for a
project with a genuinely cross-platform CI matrix.

Chosen instead: `scripts/run_complexipy.py`, a Python wrapper
setting `PYTHONUTF8` via `os.environ` before invoking `complexipy`
as a subprocess. Works identically on every OS `language: python`
already guarantees a Python interpreter for, no shell-specific
quoting or syntax involved.

### The tool pyrigor runs two self-checks, pinned and local, not just one

A single self-check, running only the current local/uncommitted
code, would never actually prove the *released, installable* package
works the way an external adopting project would use it, real
packaging or manifest issues (like `.pre-commit-hooks.yaml` being
missing from a given release, found and fixed this session) would go
undetected. A single self-check running only the pinned, released
version would lose the opposite, real, proven value: pyrigor’s own
new rules have repeatedly caught real bugs in pyrigor’s own
in-progress source the moment they were built, before any release
existed. Kept both, deliberately, rather than choosing one.

### Pre-commit hooks scope to changed files unless a tool genuinely needs whole-project context

`.pre-commit-config.yaml` mixes two real scoping models across its
hooks — most run against only the files that changed (pre-commit's
own default, no `pass_filenames: false`), a smaller set force a
whole-project scan every commit (`pass_filenames: false`, usually
with fixed directory `args:`). This was never a deliberate,
documented split. Auditing the actual file found it already mostly
matches a real principle, just never named.

Changed-files-only, correctly: `ruff`, `ruff-format`, `gitleaks`,
`actionlint`, `bandit`, `codespell`, `markdownlint-cli2`,
`complexipy`, `pylint`, `text-hygiene`, and the published, pinned
`pyrigor` hook. Every one of these produces findings that are
strictly local to the files it looks at. Nothing about an
untouched file's own cleanliness can change from editing a different
one, so re-checking it on every commit would be pure waste.

Whole-project, always, correctly: `ty`, `mypy`, `pyright`,
`radon-maintainability`, `xenon` (both entries), `tach`,
`uv-lock-check`, `dod-check`, `generate-rule-table`, `pip-audit`,
`pytest`, and the local, 'wip' `pyrigor` self-check (see "The tool
pyrigor runs two self-checks" above for why that one and the
published one are scoped differently on purpose). Each
needs cross-file or whole-program context to be completely correct: type
inference across module boundaries, module-boundary enforcement
itself, lock-file consistency against the full dependency set, a
generated file that must reflect every real guideline doc, an
environment-wide dependency audit and a test suite where a change in
one file can break a test that lives in another. Scoping any of these
to only the changed files would make them wrong, not just faster.

`pylint` looks miscategorized, sitting in the "Type/correctness
checkers, the fastest first" comment block beside three whole-project
neighbors, but it is correctly changed-files-only — pylint checks one
file at a time, same as ruff. Left as-is, deliberately, not "fixed"
into whole-project.

Three tools — `vulture`, `radon-maintainability`, and the strict
`xenon` — hardcoded directory allowlists (`pyrigor scripts tests`,
or a subset — radon's list was even missing `scripts/`), so each
silently stopped covering any directory added later. Confirmed real:
`manual-tests/` was never scanned by any of the three. Running the
tool vulture against the directory at once found three hits
(`nested_function`, `café`, `unused_pair`) — but testing each fixture
file individually, in isolation, told a fuller story: five of the six
files have a real finding, not three. The other two (`clean.py`'s
`add`, `suppressed.py`'s `apply_correction`and `violations.py`'s
own `run`) only looked used in the whole-directory scan because of
coincidental name collisions elsewhere in the codebase — a real
`run()` in `pyrigor/checkers/cli.py`, and `apply_correction`/`add` as
pyrigor's own pervasive example-function names reused across several
real test files. Vulture's unused-detection is name-based, not
scope-aware, so it cannot tell those apart from a fixture's own
same-named function — a fragile basis for narrowing, since renaming
`cli.py`'s `run()` would silently start flagging `violations.py`'s
own `run()` too, for a reason unrelated to that fixture's own
content. Every fixture's entry point is invoked externally by the
pyrigor CLI, never referenced from anywhere else in the corpus, the
same property already established for pyrigor's own self-check
exclusion of these files. A real, per-file property confirmed by
isolated testing, not an artifact of scanning them together. Running
radon and xenon against the directory found nothing — trivial
one-line fixtures do not trip complexity or maintainability
thresholds, so unlike vulture, no exclusion was needed for either.

`ty`, `mypy`, and `pyright` don't have this problem: confirmed
empirically (`mypy .` reports checking exactly 44 source files, never
touching `.venv`), all three have real, built-in smart defaults that
skip virtual environments and build artifacts without any
configuration. Vulture's own `--help` says plainly it has none: "For
each directory Vulture analyzes all contained `*.py` files."

Fixed by pointing all three at the project (`.`) instead of a
hardcoded allowlist, with an explicit, evidence-based denylist.
All three exclude `.venv`, `htmlcov`, and `*.egg-info` (never real
source). Vulture also excludes `manual-tests` with `--exclude`, while
radon and xenon use `--ignore` for the same patterns. Verified
empirically for each: identical results to before, now covering
`scripts/` (radon missed it initially) and `manual-tests/` (all three
missed it) that were previously invisible.

`xenon-shared`'s own single-file list and `tach.toml`'s `[[modules]]`
list are deliberately not touched by this — both are curated by
design, not incidental directory discovery. A new file earning a
relaxed complexity threshold, or a new package joining tach's
dependency graph, should require a real decision each time, not
silently inherit coverage the way a lint scan should.

### Self-hosted hook version lag is permanent and accepted, not a bug to fix

`.pre-commit-config.yaml`'s self-hosted `jarl-hoyem/pyrigor` hook pin
trails the actual released version by one release, structurally, not
just occasionally (#21). The `version_sync.py` only re-syncs pins when a
version bump is freshly staged in `pyproject.toml` — by the time a
new tag exists on GitHub (after the release commit is pushed and the
release published), there is no staged bump left to trigger a
re-sync. The mechanism cannot close this gap on any later commit.

Considered: a separate, scheduled workflow periodically checking
whether the pinned rev matches the latest GitHub release and opening
a PR to bump it, similar in spirit to `pre-commit-autoupdate.yaml`
but targeted at this one pin.

Chosen instead: accept the one-release lag as permanent, and
document it explicitly where a reader would actually notice the
drift (`.pre-commit-config.yaml`'s own comment), not only in
`version_sync.py`'s docstring as before. A dedicated scheduled
workflow is a real, ongoing maintenance surface for a cosmetic gap. The
pinned entry's whole purpose is confirming the released package
works the way an external adopter would use it, which it still does
correctly one version behind. Revisit only if a real consumer is
ever confused by the lag in practice, not preemptively.

### Pyrigor’s suppression comment must come last when stacked with another tool’s

The regular expression in `_suppressed_tokens()` (`#\s*pyrigor\s*:\s*(?P<tokens>.+)$`)
captures everything after `# pyrigor:` to the end of the line as the
reason. Stacking another tool’s suppression comment (`# nosec`,
`# complexipy: ignore`) after pyrigor’s own gets silently absorbed
into that reason text, since `body.partition("#")` only splits once.

Considered fixing the parser instead, truncating the reason at the
next `#` regardless of what follows. Rejected — this would break a
legitimate case: a reason referencing a GitHub issue number, for
example `# pyrigor: 406 # see issue #42`. Truncating trades away real
information to guard against a risk that, checked directly, has no
current observable effect. The function `filter_suppressed()` never
reads a reason’s content, only checks whether it is None.

Chosen instead: a house convention, not a code change. Pyrigor’s own
suppression comment goes last when stacked with another tool’s
(`# nosec  # pyrigor: PYR402 # reason`, not the reverse). The
opposite ordering already works correctly, since `re.search` finds
`# pyrigor:` wherever it appears on the line — this convention costs
nothing beyond documenting it.

### Suppression scanning uses tokenizing, not raw-line regular expression

`_suppressed_tokens()` and the near-miss check both used to search
each candidate physical line’s raw text via regular expression
(`_SUPPRESSION_PATTERN`, `_NEAR_MISS_PATTERN`), with no awareness of
Python’s lexical structure. A string literal or docstring whose
contents happened to exactly match `# pyrigor: CODE # reason` syntax
would not just trigger a spurious near-miss warning — it could
silently suppress a real violation on that line, since regular expression over
raw text cannot tell a genuine comment from text that merely looks
like one inside a string. Found scanning `tests/` for the first
time: a near-miss warning fired on a test’s own fixture string
containing literal `# pyrigor` text, not a real comment (#41).

Chosen fix: tokenize the source once per every file with Python’s own
`tokenize` module, and build a line-number-to-comment-text mapping
from genuine `tokenize.COMMENT` tokens only. String and docstring
content is tokenized as `STRING`, never `COMMENT`, so text that only
looks like a suppression comment inside a string can no longer match
at all. Candidate-line lookup changed from list-indexing raw source
lines to a dict lookup on this map, which also removes the need for
the old `_line_at()`’s explicit out-of-range bounds check — a
missing dict key returns "", the same "no comment here"
result an out-of-range line used to require special-casing for.

Rejected: keeping the regular expression approach and trying to special-case
strings within it (for example, stripping string literals from each
line before searching). Would need to reimplement a real Python
tokenizer piecemeal to handle multi-line strings, f-strings and
escaped quotes correctly — strictly more code and later risk than
just using the tokenizer the standard library already provides for
exactly this purpose.

### Suppression syntax drops the colon after "pyrigor" (permanent change)

`# pyrigor: CODE # reason`'s colon collides with ruff's `ERA001`
(commented-out-code) when the suppression comment sits on its own
line (the line-above form): `ERA001` only inspects standalone
comments, and its actual detection mechanism is an attempt to parse
the comment text as real Python (`parse_module(line).is_ok()`).
`pyrigor: 402` parses successfully as a bare variable annotation
statement (`name: value`), so `ERA001` flags it as commented-out
code. Confirmed directly against a real, installed ruff 0.16.3, not
just inferred: `# pyrigor: 402 # reason` on its own line is flagged.
Whereas `# pyrigor 402 # reason` (space instead of colon) is not.

Considered: requesting pyrigor’s own comment prefix be added to
ruff's `ALLOWLIST_REGEX`, the mechanism `# noqa`, `# nosec`, `# type:
ignore`, and others already use to avoid exactly this collision.
Rejected — not contacting ruff’s maintainers to request inclusion,
so this is not a path being pursued.

Chosen instead: drop the colon permanently. `# pyrigor CODE[,CODE] #
reason`. The regular expression's `\s*:\s*` between "pyrigor" and the token list
becomes `\s+`, requiring only whitespace, not a colon. This is a
genuine, permanent syntax change, not a temporary workaround. Every
existing colon-based suppression comment (in this project’s own
source and in any external adopters) needs migrating. An
un-migrated old comment does not fail silently: `_NEAR_MISS_PATTERN`
still matches it (a colon is not whitespace, so it no longer matches
`_SUPPRESSION_PATTERN`, but "pyrigor" is still present), so it prints
the existing near-miss warning rather than suppressing
nothing. Closes #46.

## The magic_value pylint extension: Real, independent corroboration of PYR203’s boundary

Enabled in pyrigor’s own pyproject.toml. Default valid-magic-values
(0, –1, 1, "", `"__main__"`) match PYR203’s own chosen exemption
list (0, 1, –1) independently. Real corroboration of the boundary is
reasonable, not an accident. Narrower scope than PYR203, though,
only fires on comparisons (if x == 3), not arithmetic or function
arguments.

Kept running even once PYR203 ships, deliberately, not disabled.
The same precedent is already established in this project: mypy, pyright
and ty all run simultaneously despite real overlap in what they
catch, genuine defense in depth from independent implementations,
not wasted duplication.

### The tool pylint's check-quote-consistency rejected, real false positives found

Tested empirically against pyrigor's own real source: two "findings,"
both false positives, single quotes nested inside a double-quoted
f-string's expression (`f"pyrigor {version('pyrigor')}"`,
`f"...{', '.join(...)}"`), required on this project's own supported
minimum Python (3.11, pre-PEP 701, cannot nest the same quote
character inside an f-string's expression). The  `ruff-format` already
correctly, intelligently leaves these alone, quote-nesting-aware.
Enabling this setting would actively fight correct, necessary code,
not just duplicate `ruff-format`. Rejected, not enabled.

### The tool pylint's 'allow-global-unused-variables' rejected, real false positives found

Initial testing was flawed, tested only under the setting's own
default (true, permissive), never actually verified the flipped
value. Once genuinely set to false: flags every module-level
function as an "unused variable" unless it is called within its own
defining file, exactly the wrong behavior for this codebase, which
is built on small, individually importable, individually testable
functions (find_violations, walk_once, count_parameters and every
other checker function). Rejected, not enabled.

## The tool pyrigor’s own suppression works anywhere in a wrapped statement’s span, deliberately

Confirmed the contrast directly tonight: suppressing ruff’s S607/S603
findings on wrapped `subprocess.run(...)` calls required getting the
`# noqa` onto the *exact* physical line ruff’s own diagnostic
pointed to, sometimes the opening line, sometimes the arguments
line, easy to get wrong (happened twice in one session). Same
friction hit earlier with the tool bandit’s own `# nosec`, same-line only, no
tolerance at all.

The tool pyrigor’s own suppression mechanism, by design, does not have this
fragility. A `# pyrigor CODE # reason` comment works on the line
above the violation, or on any line within the violation’s own
`end_line` span, not just one exact physical line. Confirmed by,
`test_suppression_comment_on_middle_line_of_multiline_statement_suppresses`. And confirmed by
`test_suppression_comment_on_closing_line_of_multiline_statement_suppresses`.

Worth stating this explicitly as a real, deliberate design advantage
in the README.md or the eventual suppression-syntax reference doc, not
just an implicit property. Adopters coming from the ruff/bandit’s own
stricter placement rules will likely appreciate knowing this
up front.

## The tool ruff’s select = ["ALL"] adopted, with a real, evidence-based ignore list

Considered simply picking a curated set of categories versus
enabling everything and reviewing what comes back. Chose "ALL" plus
a deliberate ignore list, following Pickomino’s own real precedent
(confirmed directly from its pyproject.toml), rather than guessing
at categories in the abstract. Every ignored rule has a real,
specific reason (D203/D213/D413 conflict with the chosen docstring
convention, COM812 conflicts with the formatter, EM101/EM102/TRY003
reflect this project’s own no-custom-exception-hierarchy style,
CPY001 has no adopted copyright convention). Verified empirically at
each step (427 findings raw, resolved category by category down to
16 real, individually reviewed fixes) rather than trusting the
ignore list’s own reasoning without checking real output.

## Dev-tooling scripts share real logic via a `check: bool` parameter, not a hardcoded default

The file check_definition_of_done.py and version_sync.py both needed the
identical git-diff-inspection logic (staged_files,
pyproject_version_changed), found as genuine duplicate code by
pylint’s own R0801, not just an incidental shared literal (unlike
the filename-constants decision, which stayed local per script).
Extracted into scripts/_dev_tooling_shared.py.

The two callers need genuinely different failure behavior, though:
check_definition_of_done.py explicitly promises "never fails the
commit" in its own docstring, so a real git failure should not
crash it (check=False). The file version_sync.py makes no such promise and
already has a real, intentional failure path (sys.exit(1)), so a
real git failure surfacing (check=True) is more honest than
silently continuing with empty data. Rather than hardcode one
behavior into the shared functions, check is a required keyword
argument, letting each caller express its own actual philosophy.

### Branch protection on main was verified via a real test pull request

This was not just the API response.

#19 added branch protection (13 required checks from `ci.yaml`, 1
required review, strict mode) via a direct `gh api` call. The API
response confirmed the settings were accepted. But that only proves
GitHub stored the configuration, not that it behaves as
intended — this repo had zero human-authored PRs before this point
(all five prior PRs were Dependabot’s), so the mechanism had never
actually been exercised.

Verified directly, this very entry is the content of that test PR:

- All 13 required checks ran and passed. `mergeStateStatus` stayed
  `BLOCKED` and `reviewDecision` stayed `REVIEW_REQUIRED` anyway —
  green checks alone do not satisfy the review requirement, the two
  gates are genuinely independent.
- A wrong assumption caught in the process: self-approval is not an
  org-only restriction. GitHub blocks a PR’s own author from
  approving it as a baseline rule — confirmed directly, the author
  hit this in the real GitHub UI, not inferred from documentation.
  Exactly which review-related settings *are* org-specific (versus
  this universal one) was not re-verified and should not be assumed
  either way without checking again.
- Practical consequence for a solo maintainer: `enforce_admins:
  false` is what actually makes merging your own PR possible at all
  right now, via the "merge without waiting for requirements"
  administrator-bypass path, not by approving your own work. #56 (move to
  an org once a second contributor exists) still stands, corrected
  to reflect this. The real gap is not "self-approval is allowed,"
  it is "the only way to merge solo is an administrator override that skips
  the review gate entirely."

### `ruff format` adopted over `black`, confirmed empirically not assumed

Real comparison run against this project's own source (`pyrigor/`,
`scripts/`, `tests/`), not assumed from either tool's reputation:
`black --check --diff` (matching `line-length = 120`) found exactly
one real disagreement — a blank line `black` wants inserted after a
module docstring immediately followed by a comment. Fourteen files, always
the same single-line pattern, nothing else. Output is otherwise
identical.

Timing on the same run: `ruff format --check` finished in 0.24 s,
`black --check --fast` in 4.43 s — 18x, though at this
codebase's small size that gap is dominated by `black`'s own
Python-interpreter startup cost, not necessarily per-file work. The
direction (ruff, written in Rust, faster) is real and expected, the
exact multiple is not a claim about the scale.

Chosen for both reasons together, not either alone: near-identical
output removes any real formatting-preference cost to switching, and
`ruff` is already a required dependency for linting (`select =
["ALL"]`) — `ruff format` adds zero new tools or config surfaces,
where `black` would be a second, separate tool doing overlapping work.

Real history behind this, not just the comparison above: `black` and
`ruff` fighting circularly, each run undoing the other's formatting
choice, was a genuine, repeated problem before `ruff format` replaced
`black` outright, with smaller versions of the same fight against
`isort` too. It traces back further than this project: the same
shape of conflict, PyCharm's own built-in formatter against `black`,
is where this whole line of tool-configuration discipline actually
started, in Pickomino (see the "Pickomino inheritance audit"
milestone) — `black` won that round. The tool `ruff` won the next one.
Consolidating onto one tool per job, instead of layering several with
overlapping opinions, came from living through both, not from reading
about either.

### xenon's two-tier grade system

The tool xenon has no per-function suppression mechanism, unlike complexipy's
inline `# complexipy: ignore`. The `xenon-shared` hook (relaxed to
grade B) exists specifically for files with a documented, real
exception (currently `_shared.py`'s `walk_once`, see the 'ast.walk'
entry above), while the default `xenon` hook stays at strict grade A
for everything else. A file only qualifies for the relaxed hook once
it has its own DECISIONS.md-documented reason, not by default.

### The tool vulture's confidence threshold

Kept at its default (60), deliberately, not tuned. Real runs against
pyrigor/, scripts/, tests/ and manual-tests/ produced zero false positives at this
threshold, no evidence raising it would help, and raising it risks
missing genuine dead code. (Per-file isolation testing of the manual-test
fixtures revealed real unused findings in five of six files. They only
appeared "used" in whole-directory scans because of name collisions with
real code elsewhere, a fragile basis for any narrowing.)

### `tach` adopted for module-boundary enforcement, real boundaries from real architecture

`tach check` ran clean, zero findings, against a `tach.toml` marking
every individual `pyrXXX_*.py` checker as its own isolated module
(never importing another checker, only
`_shared.py`/`rules.py`/`violations.py`), `_shared.py` and `cli.py`
each as their own module, and `scripts/`/`tests/` each as one coarse
module separate from the real package. The clean result confirms
these boundaries were already followed informally. Adopted despite
finding nothing today, for its preventive value against a future
accidental import, matching this project's own stated philosophy
(README.md: "Do not rely on convention or code review where a tool
can enforce correctness instead") — not because a current violation
demanded it. See #7.

Real, ongoing cost: `tach.toml` needs updating whenever a new
`pyrXXX` checker is added, or the new file silently falls outside
`tach check`'s tracking — `ADDING_A_RULE.md`'s own checklist gained a
step for this.
