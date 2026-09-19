# Design and architecture decisions

A running log of _why_ a structural choice was made, not just the result. Read this before asking "why does the code do
it this way" rather than re-deriving the reasoning from scratch.

## Testing and release confidence

### Adversarial test matrices and installed-artefact checks are complementary

The PYR406 torture-test pass found real defects in lexical binding: later lambda and import rebinding,
comprehension-local targets and class-body bindings all produced incorrect results until tested as deliberate
combinations. The lesson is broader than PYR406: test the behaviour an adversarial reader would try to break, not only
the happy path or the line that motivated the change.

The same pass also verified the built wheel and source distribution in isolated environments. The editable checkout had
already passed, but that could not prove the release artefacts contained the right modules and entry point. The
source-level matrices and installed-artefact smoke tests are separate confidence layers. Neither replaces the other.

## pyrigor architecture and rules

### NamedTuple and NewType close different gaps

NamedTuple for returns, NewType for same-typed values at risk of confusion.

Rule:

Always use NamedTuple for any function returning more than one value. This removes positional-unpacking ambiguity. The
caller accesses fields by name (result.dj_dw), not position, so a mislabelled variable at the call site can no longer
silently receive the wrong value.

Use NewType for any same-typed values, whether function arguments or NamedTuple fields, that could plausibly be swapped
or confused (for example, Weight/Bias when both might be represented as float or a same-shaped ndarray). Skip it where
confusion is not realistically possible.

Why:

Different-typed arguments (for example, w: np.ndarray, b: float) are already protected by mypy, a swap at the call site
is a type mismatch and gets caught. No NewType needed here.

Same-typed arguments (for example, two float parameters) are not protected by mypy alone. Both are structurally
identical, so a swap is a silent, valid-looking call. NewType makes them nominally distinct, so mypy catches the swap.

NamedTuple closes a separate gap: even with a fully typed multi-value return (for example, tuple[np.ndarray, float]),
mypy checks the type at each position but not the name the caller gives it. A caller can unpack into misleadingly named
variables (dj_db_temp, dj_dw_temp = ... when the function actually returns dj_dw, dj_db), and mypy will not catch it,
because the types still line up positionally, only the semantics are wrong. This is a silent bug that surfaces only when
the mislabelled variable is later used in a way that exposes its true type. For example, calling '.tolist()' on an
assumed float, a runtime crash, not a caught error.

NamedTuple field access removes the positional slot entirely, so there is nothing to mislabel.

Combined, these two will catch:

- Argument-order swaps for differently typed args: plain type annotations (no extra tooling needed).
- Argument-order swaps for same-typed args: NewType.
- Return-unpacking mislabelling for differently typed return values: NamedTuple alone.
- Return-unpacking mislabelling for same-typed return fields: NamedTuple and NewType together.

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

Every checker originally called `ast.walk(tree)` independently, once per checker per the file. Profiling against the
Home Assistant core (18,187 files) found this was the dominant cost: `ast.walk` itself accounted for 286 of 388 seconds,
and the cost scaled linearly with the number of registered checkers, every future rule added would make it worse.

Two designs were considered.

**Cache-based** (rejected): keep every checker's own `find_violations(*, tree)` signature exactly as-is, walk once
inside `_run_checkers` and cache the result keyed by `id(tree)`, so a repeated internal `ast.walk` call inside
`_shared.py` would hit the cache rather than re-walking. Smaller diff, no signature changes anywhere. Rejected because
it is exactly the kind of implicit, hidden coupling this project has repeatedly been burned by — the
`zip(CHECKERS, Rule)` positional-coupling bug fixed earlier is the same category of problems. It rests on an unenforced
assumption: "every checker always walks the same cached tree." It also does not remove the actual walk cost — it only
hides one walk behind a cache lookup. Real savings would require every future checker's own logic to want the tree
walked in the same way, silently broken the moment one does not.

**Nodes-based** (chosen): walk the tree exactly once in `_run_checkers`, via `walk_once()`, producing a
`WalkedNodes( function_nodes, assign_nodes)`. Every checker's own public `find_violations` signature changes from
`(*, tree: ast.Module)` to `(*, nodes: WalkedNodes)`, an honest interface describing exactly what each checker actually
needs, rather than "a tree, which happens to be pre-walked somewhere else by convention." Real cost: touched five
checker files, the `_CheckerFun` Protocol and every existing test calling `find_violations` directly. Real result:
confirmed via profiling, `ast.walk`'s own call count dropped exactly 5.0x (69,393,100 to 13,878,620), and real-world
timing on the same 18,187-file run dropped from 388.20 s to 55.46 s, 7x.

### PYR406 matches only bare-name calls, not attribute calls

PYR406 flags a discarded call only when the callee is a bare name (`compute_total(items)`), never through attribute
access (`self.compute_total()`, `obj.compute_total()`). Consequently, functions with a leading `self`/`cls` parameter
(methods) are excluded from the protected set entirely.

Why: pyrigor cannot reliably determine which class or object an attribute call belongs to — it has no type inference and
processes one file at a time. Without this exclusion, matching by name alone would let a method's name enter the
protected set even though nothing ever calls it as a bare name. The only effect would be a false positive on some
unrelated bare call elsewhere in the file that happens to share the method's name. Excluding likely methods removes that
risk at the cost of not covering method calls at all, consistent with the guideline doc's own examples, which are all
bare-name, module level or nested function calls.

The exclusion is by parameter name, not by scope, so a module-level function whose first parameter happens to be called
`self` or `cls` also escapes protection, a real false negative rather than the intended false-positive guard (#307,
confirmed by mutation testing rather than assumed: the name check does change the result, and stays for this reason).

The lexical-scope utilities used to resolve those bare names live in `checkers/_shared.py`, rather than in PYR406. This
is deliberate: the documented PYR407 generator-result rule has the same local-definition and bare-call boundaries and is
the planned second consumer. The shared layer provides scope structure. Each rule retains its own return-value
classification.

### The --select/--ignore combines like ruff's select/ignore, and full-overlap combination errors

`--only` was renamed to `--select` (#68), and `--ignore` was added (#69) as its rule-axis opposite, matching ruff's own
`select`/ `ignore` pair rather than inventing pyrigor-specific terms (a principle first stated on #66).

Combination semantics, verified against ruff's own documented behaviour rather than assumed: `--ignore` removes codes
from `--select`'s set (or from every rule, if `--select` is omitted). Order on the command line never matters. Argparse
collects each flag's own value independently of where it sits relative to the other flag. `_filter_checkers()`'s
combination logic is pure set arithmetic on the final parsed values, not a fold over argv in parse order. Partial
overlap (`--select=PYR401,PYR402 --ignore=PYR402`, leaving PYR401) is the intended, normal use case, matching ruff's own
documented "select a category, ignore one rule within it" pattern — not an error.

Full overlap is different in kind, not just degree — a combination that empties the selection entirely
(`--select 403 --ignore 403`) produces zero checkers to run. That is technically successful but certainly unintended,
the same failure shape `nargs="+"` already closed for zero paths (#51). The `_reject_empty_selection()` catches this in
`run()`, not inside `main()`, keeping `main()` a pure function that never touches `sys.exit()`/stderr itself. This costs
one extra, inexpensive call to `_filter_checkers()` (pure, iterating a small fixed tuple) but preserves that separation
rather than threading exit-code concerns into the library function tests call directly.

### CLI exit code 2 covers both a crash and a bad invocation, deliberately not split

When pyrigor's `run()` migrated from hand-rolled `sys.argv` scanning to `argparse` (#51), argparse's own native parse
errors (unrecognised flag, missing required `paths`) landed on exit code 2 — the same code already used for two
different pre-existing cases: an unexpected internal crash (the top-level `except Exception` handler) and a bad `--only`
invocation (repeated flag, unknown rule code). All three now share one exit code.

Decided not to split them. Reasoning: the ambiguity predates this migration — "2 means either a crash or a bad
invocation" was already the convention before argparse was introduced, so widening it to argparse's own errors is
consistent, not a new compromise. Splitting would need either a custom `ArgumentParser` subclass overriding `error()`,
or wrapping `parse_args()` in `try/except SystemExit` to remap its code — real added surface area for a distinction no
test, issue or actual consumer of pyrigor's exit code has needed yet. If a concrete need for the distinction shows up
later (for example, a CI wrapper that retries on exit 2 assuming it is transient, when a bad invocation is not). That is
the evidence to revisit this, not a preference alone.

## Fix classification: Adopt now, architecture: Defer

Considered whether current rule-building should expect a future FixProposal architecture (detect()/suggest(), a
three-tier fix classification: safe_fix/suggestion/guidance, full CLI→editor extension→Language Server Protocol (LSP)
roadmap), per a real, external strategy document (#105).

Split the decision cleanly. Documenting a real fix classification per rule costs nothing, no code changes and already
proved valuable once: working through it caught a real, initial misclassification (PYR402/PYR403 first looked unsafe due
to caller breakage, corrected once the actual, primary scenario, editor-time feedback on a function with no callers yet
was considered). Adopted as a permanent, standing part of every new rule doc's own template.

The actual FixProposal architecture itself (a real suggest() implementation, editor extensions, an LSP) is explicitly
deferred, not adopted now. Building real engineering toward editor integration for a tool with zero real external
adopters and no editor integration at all yet is exactly the kind of premature investment already identified as this
project's biggest real risk. Revisit only once real, concrete demand exists, a real user asking or genuine
editor-integration work actually starting, not before.

## Severity: Language Server Protocol DiagnosticSeverity naming adopted, real per-rule levels assigned

A real `severity` field is used by the `--output-format=json` diagnostic schema (file, line/column, rule ID, message,
severity, per `pyrigor_strategy.txt`'s own Stage 1 requirements), and nothing in pyrigor's own `Rule`/`RuleInfo`
structure provided one until now (#158).

Scheme: reused the Language Server Protocol's own `DiagnosticSeverity` naming (`Error`, `Warning`, `Information`,
`Hint`) rather than inventing pyrigor-specific terms, matching the same "match an existing tool's own naming, do not
invent" principle already applied to `--select`/`--ignore` (#66). Chosen specifically because pyrigor's own roadmap
already commits to eventual LSP integration (#152, deferred but decided) — assigning severities in LSP's own vocabulary
now means zero translation layer once that work actually starts. Used three of LSP's four levels
(`error`/`warning`/`info`, the common short form of `Information`) — `Hint` was not used, since none of pyrigor's 18
rules are pure editor-hint-level suggestions. Even the lightest-weight ones are real, considered diagnostics.

Graded by consequence severity if the underlying pattern's bug actually occurs, not by how likely that is — a rule
catching a rare but catastrophic bug outranks one catching a common but low-stakes one.

| Rule(s)              | Severity | Why                                                                      |
| -------------------- | -------- | ------------------------------------------------------------------------ |
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

Wired into `pyrigor/rules.py` for the six built rules (a `Severity` enum, not a bare string — using one here would
contradict PYR202's own point while implementing severity for it). The twelve documented-but-unbuilt rules carry their
severity in their own guideline doc only, until each is actually built, following `ADDING_A_RULE.md`'s checklist.

### JSON diagnostics are a versioned contract, not a serialization detail

The `--output-format=json` output is an editor and tooling API. Its published JSON Schema is therefore part of the API:
contract tests must validate actual output for clean results, diagnostics, suppression and operational errors. Rule
metadata such as severity and fixability has one canonical source in `RuleInfo`. Documentation and tests should detect
drift rather than duplicate the classification independently. Human output remains a separate compatibility surface.
Columns count code points. The v2 contract adds raw byte offsets alongside them because exact edits need positions in
the file as written. Unicode behaviour is covered explicitly.

### The v2 finding contract is one JSON Schema, attacked on purpose

`schemas/pyrigor-diagnostics-v2.json` is the single source of the finding types and their conventions, and it is edited
directly. A script generating it would be a second copy to keep in synch. The file `FINDING_MODEL.md` records the
reasons, and the worked position examples are checked by tests against raw bytes and Python's parser, so a direct edit
stays safe.

The model was settled by an architecture council of five independent reviews on #278: raw byte offsets with code-point
columns, an edit shape of its own, a list of fixes, an enclosing symbol for identity and an extension policy. It has no
child diagnostics, notebook cells or per-finding URL.

The schema was then attacked deliberately, in rounds. A regression test rejects every hostile input it can recognise.
Every violation it cannot recognise is pinned as accepted and listed as a producer invariant. Removing any single rule
makes a test fail. The attacks decided three things the review had not. The root rejects every document until the
wrapper exists (#288). The `uniqueItems` is not used because it made validation quadratic. Text that people see may not
contain zero-width, bidirectional control or invisible filler characters.

Earned by: the first version accepted any document at its root, a rule code with a trailing newline and absolute file
names, and took seconds to validate a finding with thousands of spans. Its tests passed because they only checked the
rules the schema's author had thought of. Portability of the patterns across regex engines is still open in #291.

### Finding types are frozen dataclasses that check themselves

The v2 finding types in `pyrigor/findings.py` are frozen, keyword-only dataclasses, not NamedTuples. A NamedTuple is a
tuple, so a span would compare equal to a plain tuple of the same values and could be unpacked by position, the
confusion PYR401 exists to prevent. A dataclass can check its invariants when it is built, so a finding with two primary
spans or a fix with overlapping edits cannot exist. Frozen keeps findings hashable, which the uniqueness checks use.

Each type rejects the structural mistakes #287 lists and the producer invariants the schema cannot express, such as
unsorted edits, a lone surrogate or a file name not in NFC. It does not repeat the schema's own rules. Validating the
serialised finding checks those, so each rule has one source.

A finding's `level` is computed from its rule instead of stored, so it cannot disagree with `code`. Byte offsets, lines
and columns are separate `NewType`s, so a column cannot be passed where a line is expected. Positions come from the raw
file bytes through a `PositionIndex` built once per file, and `make_span` is the only code that constructs a span.

### The v2 output is one JSON document, not a JSON Lines stream

JSON Lines was considered for the v2 output while the wrapper (#288) was still undefined. It would give three things:
sharded or parallel runs whose outputs merge with `cat`, bounded memory at sizes like the 90,488 findings of a key
performance indicator scan and a file that stays parseable up to its last newline after a crash.

None of the three is available today. The pipeline aggregates every file's results before printing, so nothing streams
until that changes, and no consumer reads the output in shards.

The costs are immediate. Most of the wrapper #288 defines is per-run: `schema_version`, the tool name and version,
`rules`, `errors` and `summary`. Only `findings` and `suppressed` hold findings, and they are two lists. A single stream
of records cannot tell them apart, and the per-run parts cannot appear at all, without a tag on every record. The stream
then becomes a discriminated union, and a record is no longer a `Finding`. That is the one type the schema pins down
with `additionalProperties: false` and its invariants. Validation also stops being something `check-jsonschema` or an
editor does for free. A version is worse in a stream than in a document. A consumer reads `schema_version` before
anything else in a document, but in a stream it either trusts the first record to be a header or discovers a version it
cannot handle halfway through.

The option is kept open rather than closed. The schema defines a finding and no document, so a later
`--output-format=jsonl` could emit `#/$defs/Finding` records for kept findings only, with no header, leaving the per-run
parts to the document format. Defining a JSON Lines wrapper now is what would foreclose that. Two things would justify
one: a consumer that must act on findings before the run ends, or runs sharded across workers whose outputs concatenate.

## Opt-in rule tier: Real, two independent axes, no separate numbering

Found while considering a "ban the walrus operator" rule (#163): every PYRxxx rule today is framed as eventually
default-enforced, catching a silent bug type checkers/standard linters miss. A walrus-ban does not fit that framing — it
is a genuine readability preference, not a silent-bug detector, but still a real, structurally checkable rule someone
might deliberately want (#162).

**Decision: yes, pyrigor supports a distinct, explicitly opt-in rule tier.** Real, concrete demand already exists
(#163), and MISRA — the project's own repeatedly cited inspiration — already distinguishes Mandatory/Required/Advisory
rules rather than treating an opinionated rule as beneath inclusion.

**No separate numbering namespace, unlike `PYREJECT1xx`.** First proposed a `PYROPT1xx` prefix, mirroring the
rejected-rules namespace. Rejected: `PYREJECT1xx` is safe specifically because rejection is permanent — nothing ever
moves out of that bucket. An opt-in rule's tier is not permanent in the same way: a rule might start opt-in and later
prove popular enough to go default, or the reverse. Baking tier into the number would mean renumbering on any such move,
breaking every existing suppression comment and `--select`/`--ignore` reference written against the old number — exactly
the unstable-identity problem this project has already been burned by (the `zip(CHECKERS, Rule)` positional-coupling
bug. The "rule identity flows from one place"). Opt-in rules get a normal `PYRxxx` number from `NUMBERING.md`'s existing
bucket scheme, same as any other rule.

Verified this against a real precedent rather than assuming: MISRA C itself keeps rule numbers fixed and has a formal
Guideline Re-categorisation Plan (GRP) specifically for moving a rule between Mandatory/Required/Advisory without
renumbering it — confirming number-stable, metadata-changeable is the established pattern for exactly this problem, not
an invented workaround.

**Two independent metadata axes on `RuleInfo`, not one:**

- **`Tier`: `Default` | `Advisory`** (MISRA naming). Controls real CLI behaviour: `Default` rules run without being
  selected, matching every rule today. `Advisory` rules are excluded from that implicit default set — reachable only via
  explicit `--select=PYRxxx` (or symbolic name), never by omitting `--select` (which means "run the default set") and
  never via `--ignore` alone (which only removes codes from an already-selected set. An `Advisory` rule was never in
  that starting set).
- **`Maturity`: `Stable` | `Preview`** (Ruff naming, checked against Ruff's own docs rather than assumed). A genuinely
  different axis from `Tier` — how proven a rule is, independent of whether it is meant to be universal or opinionated.
  All six built rules are retroactively `Stable`, already proven through this project's own dogfooding history.
  `Preview` is documentation-only for now, no CLI flag of its own — it does not gate whether a rule runs. `Tier` alone
  does that. Not adding Ruff's `Deprecated`/ `Removed` states or a `--preview` CLI switch: no rule has ever needed
  either, and building them speculatively would repeat the premature-investment mistake the FixProposal deferral above
  already identified. Add them later if real demand shows up, not now.

## Development process and tooling

### Do not duplicate rules already covered by existing tools

The tool pyrigor fills gaps that existing quality tools do not cover. It does not implement a second checker for a
pattern that an existing tool already detects, even when that tool requires an explicit configuration. The covering tool
should be documented instead, and the proposed pyrigor rule should be recorded in `REJECTED.md`.

This applies to missing docstrings on private functions and methods: Pylint's `missing-function-docstring` (`C0116`)
detects them when `no-docstring-rgx` is configured to exempt no names. PyCharm also reports the issue. A dedicated
pyrigor rule would therefore duplicate existing tooling. Missing docstrings on nested functions remain a separate
question because Pylint does not report them.

### Fixer interface: explicit selection, in-place fix, diff preview

The first fixer is exposed through `--fix --select PYR402`, with `--diff` providing a non-writing unified-diff preview.
Both `--option value` and `--option=value` forms are accepted because they are equivalent argparse interfaces users
reasonably expect.

Fixer modes require explicit PYR402 selection. Unlike a general-purpose linter that may fix every rule marked safe,
pyrigor's PYR402 transformation can make existing positional calls fail at runtime. Requiring the rule in the command
makes that behaviour deliberate and auditable. Rejected or unsupported source is reported and left unchanged; the fixer
never inserts automatic suppressions. Source bytes, UTF-8 BOMs and line endings are preserved wherever the source can be
decoded as UTF-8.

### Fixer encoding boundary: reject non-UTF-8 sources

The PYR402 fixer explicitly rejects source files that cannot be decoded as UTF-8, including other declared source
encodings. Python 3.11+ support does not make arbitrary source encodings safe on the round-trip: encoding detection,
rewriting and byte preservation would each need separate guarantees. Leaving an unsupported file unchanged is safer than
risking corruption. Broader source-encoding support is deferred to a separate design decision.

### Tool findings: Fix, then suppress narrow before broad

Real, six-step order, not "fix or ignore": **fix → line suppress → function suppress → file suppress → folder suppress →
project exclude.** Each step moves down this list only once the narrower option genuinely does not fit — never skipped
to for convenience.

Why the order matters: each step hides more code from a tool's own scrutiny than the last. Line suppression affects one
line. A function-level exemption (complexipy's own `# complexipy: ignore`) still leaves the rest of that file checked. A
file-level exemption (xenon-shared, scoped to `_shared.py` by name) means nothing in that one file is checked by that
tool again — but everything else still is checked. A folder-level exemption (ruff's own `per-file-ignores`: `"tests/**"`
for `S101`/`PLR2004`, since `assert` is pytest's own idiom and a literal comparison is the test's own job, not a magic
value. The `"scripts/**"` for `T201`, since `print` is a standalone script's real output) is broader still, exempting
every file a whole directory ever contains, present or future — a real, deliberate reason at the directory's own scope,
not one file's. A project-wide exclude (`markdownlint`'s `MD018` disabled outright) means no file anywhere, ever, is
checked for that pattern — the largest, most permanent blind spot a tool-finding response can create, reserved for when
the finding itself is wrong for the project, not just wrong in one spot.

This was not decided in the abstract — it is the pattern this project's own real decisions already follow, named
explicitly here for the first time rather than left implicit. Each level above has a real, already-adopted precedent,
not a hypothetical one.

### GitHub Issues are referenced as a bare `#N`, never a linked title

Now that `BACKLOG.md` is retired and every real work item lives as a GitHub Issue, `DECISIONS.md` and
`REVIEW_CHECKLIST.md` needed a single, deliberate convention for referencing one, rather than an adhoc choice made
differently each time (#101).

Checked the actual, current practice across both files first, rather than picking a convention in the abstract: every
existing reference in `DECISIONS.md` already uses a bare `#N` (`(#68)`, `on #66`, `#19 added...`,
`#56 (move to an org...) still stands`), sometimes with a short inline parenthetical gloss when the number alone would
not orient an unfamiliar reader, sometimes without. The file `REVIEW_CHECKLIST.md` has no issue-number references at
all.

Chosen: keep the already-consistent bare `#N` form, with an optional short parenthetical gloss at the author's own
discretion for a number a reader is unlikely to recognise on sight. Not a linked Markdown title — GitHub already
auto-links a bare `#N` inline within its own rendering, so a manual `[title](url)` link would be a redundant markup for
zero real benefit, and would also silently go stale if the issue's title is ever edited later.

No retrofit needed: every existing reference in both files already matches this convention.

### The tool complexipy runs through a Python wrapper, not a .bat script

The tool complexipy's own console output (via `rich`) crashes on Windows' legacy `cp1252` codepage when printing status
emoji, confirmed across two different pinned versions (an octopus at v3.0.0, a checkmark at v7.0.1), a genuine, systemic
upstream bug, not fixed between releases.

A Windows batch script (`scripts/run_complexipy.bat` setting `PYTHONUTF8=1` before invoking the binary) was considered
first, and would have worked locally. Rejected because it is Windows-only, `.bat` syntax and `%*` argument forwarding
mean nothing on macOS or Linux, and this project's own CI matrix explicitly tests `ubuntu-latest`, `macos-latest` and
`windows-latest`. A fix that only works for one contributor's own OS is not a real fix for a project with a genuinely
cross-platform CI matrix.

Chosen instead: `scripts/run_complexipy.py`, a Python wrapper setting `PYTHONUTF8` via `os.environ` before invoking
`complexipy` as a subprocess. Works identically on every OS `language: python` already guarantees a Python interpreter
for, no shell-specific quoting or syntax involved.

### The tool pyrigor runs two self-checks, pinned and local, not just one

A single self-check, running only the current local/uncommitted code, would never actually prove the _released,
installable_ package works the way an external adopting project would use it, real packaging or manifest issues (like
`.pre-commit-hooks.yaml` being missing from a given release, found and fixed this session) would go undetected. A single
self-check running only the pinned, released version would lose the opposite, real, proven value: pyrigor's own new
rules have repeatedly caught real bugs in pyrigor's own in-progress source the moment they were built, before any
release existed. Kept both, deliberately, rather than choosing one.

### Mutation testing runs under tini and disables coverage through mutmut's own config

Two failures made mutmut unusable in Docker, both caused by configuring something mutmut never read.

The tool mutmut 3.7 has no `tests` config key. Its `_load_config()` reads `pytest_add_cli_args` and
`pytest_add_cli_args_test_selection`. A `tests = "pytest ... -c pytest-mutmut.ini"` line is accepted silently and
discarded, so every attempt to disable pytest-cov through it changed nothing. Four rounds of workarounds followed,
ending in a repository-wide `--cov-fail-under=0`, which switched off this project's own 100% coverage gate for every
ordinary test run. Fixed by passing `--no-cov` through `pytest_add_cli_args`, which mutmut appends after the copied
`pyproject.toml`'s `addopts`, so it wins, leaving the repository's own threshold at 100. The tool pytest-cov stays
installed on purpose. Uninstalling it makes `--cov=pyrigor` in `addopts` an unrecognised argument, pytest exits 4, and
mutmut raises `BadTestExecutionCommandsException`.

Coverage must be off during mutant runs, not merely set below a threshold. Every mutant run invokes pytest with `--cov`,
and coverage writes its data file into the working directory. Under mutmut's parallel children those writes collide,
pytest exits non-zero and mutmut records a kill that the mutation did not cause. Such false kills only ever inflate the
score, and they scale with the number of cores.

Measured on one commit: 6 survivors with coverage enabled, against 288 with `--no-cov`. A CI runner with fewer cores
independently reported 275. The proof is a provably equivalent mutant, which rewrites `version('pyrigor')` as
`version('PYRIGOR')`. Distribution name lookup is case-insensitive, so no test can detect it, yet the coverage-enabled
run reported it killed. Rerunning that one mutant alone showed it surviving. Disabling coverage is also 57% faster.

An earlier version of this entry blamed `pytest_add_cli_args_test_selection` for the 288 survivors. That was wrong. The
key was innocent, and 288 was the honest number, briefly discarded in favour of a flattering one.

The second failure was `KeyError: <pid>` in `read_one_child_exit_status()`, which calls a bare `os.wait()` and then
indexes `source_file_mutation_data_by_pid[pid]`. As the container's entrypoint, mutmut runs as PID 1, so every orphaned
process in the container is reparented to it, and this test suite spawns real `git` and `python` subprocesses. The tool
mutmut then reap a pid it never forked and crashes. Running `docker run --init` fixes it, but only when every call site
remembers the flag. Installing tini and making it the entrypoint makes the image correct on its own, including for an
ad-hoc `docker run`.

### Mutation testing gates on a score floor, not on zero survivors

The command `mutmut run` returns normally after printing its summary and never sets an exit code from the results, so a
job that only runs it cannot fail on survivors. The workflow exports stats with `mutmut export-cicd-stats` and runs
`scripts/check_mutation_score.py`, which fails below an 80% floor.

The floor is 80% because the honest score is 81.63%, with 288 surviving mutants. Earlier floors of 99.5% and then 99%
were set against measurements inflated by the coverage false kills described in the entry above. Those runs reported two
to six survivors, which was never real. Raise this floor as the suite improves, in a step with a measured score rather
than an assumed one.

A zero-survivor gate was rejected because it is unreachable. The mutant rewriting `version('pyrigor')` as
`version('PYRIGOR')` survives permanently. Distribution name lookup is case-insensitive, verified directly, with both
spellings returning the same version. Only a test that mocks the lookup and asserts the literal argument could kill it,
and such a test pins the implementation rather than the behaviour. This mutant is also the one that exposed the false
kills, because a coverage-enabled run claimed to have killed something no test can detect.

Timeouts leave the denominator entirely. They track the machine load, not test quality. Two appeared in one local run
only because other containers were competing for the processor.

A recorded baseline of known survivors would catch a single new survivor, which a floor cannot. That option stays open
once the run-to-run variance is understood. A survivor baseline fails closed, so it is not the kind of path allowlist
this project rejects.

### Pre-commit hooks scope to changed files unless a tool genuinely needs whole-project context

`.pre-commit-config.yaml` mixes two real scoping models across its hooks — most run against only the files that changed
(pre-commit's own default, no `pass_filenames: false`), a smaller set force a whole-project scan every commit
(`pass_filenames: false`, usually with fixed directory `args:`). This was never a deliberate, documented split. Auditing
the actual file found it already mostly matches a real principle, just never named.

Changed-files-only, correctly: `ruff`, `ruff-format`, `gitleaks`, `actionlint`, `bandit`, `codespell`,
`markdownlint-cli2`, `complexipy`, `pylint`, `text-hygiene` and the published, pinned `pyrigor` hook. Every one of these
produces findings that are strictly local to the files it looks at. Nothing about an untouched file's own cleanliness
can change from editing a different one, so re-checking it on every commit would be pure waste.

Whole-project, always, correctly: `ty`, `mypy`, `pyright`, `radon-maintainability`, `xenon` (both entries), `tach`,
`uv-lock-check`, `dod-check`, `generate-rule-table`, `pip-audit`, `pytest` and the local, 'wip' `pyrigor` self-check
(see "The tool pyrigor runs two self-checks" above for why that one and the published one are scoped differently on
purpose). Each needs cross-file or whole-program context to be completely correct: type inference across module
boundaries, module-boundary enforcement itself, lock-file consistency against the full dependency set, a generated file
that must reflect every real guideline doc, an environment-wide dependency audit and a test suite where a change in one
file can break a test that lives in another. Scoping any of these to only the changed files would make them wrong, not
just faster.

The two complexity tools are the arguable pair, and scoping them was tried and rejected on 2026-09-18. A maintainability
index and a complexity rank are both per file, so a changed-files run would give the same verdict. Measured, it saved
about 0.9 seconds of a 16-second commit. Against that, `radon-maintainability` broke outright, because its `--allow`
entries must name a file that was checked, which is how a stale entry fails once #268 removes the need for it. The
strict `xenon` worked, but it would have left `vulture` and `radon-maintainability` on
`scripts/run_on_git_python_files.py` while one tool of the three used pre-commit's own list, and that list holds tracked
files only, where the script also covers untracked ones. One file-list mechanism for all three is worth more than the
second it buys.

`pylint` looks miscategorized, sitting in the "Type/correctness checkers, the fastest first" comment block beside three
whole-project neighbours, but it is correctly changed-files-only for the same reason as ruff: most of its findings are
local to one file. One real exception exists, `duplicate-code` (R0801), see "Pylint's duplicate-code check needs
`require_serial`" below. Left changed-files-only, deliberately, not "fixed" into whole-project.

Three tools — `vulture`, `radon-maintainability` and the strict `xenon` — hardcoded directory allowlists
(`pyrigor scripts tests`, or a subset — radon's list was even missing `scripts/`), so each silently stopped covering any
directory added later. Confirmed real: `manual-tests/` was never scanned by any of the three. Running the tool vulture
against the directory at once found three hits (`nested_function`, `café`, `unused_pair`) — but testing each fixture
file individually, in isolation, told a fuller story: five of the six files have a real finding, not three. The other
two (`clean.py`'s `add`, `suppressed.py`'s `apply_correction`and `violations.py`'s own `run`) only looked used in the
whole-directory scan because of coincidental name collisions elsewhere in the codebase — a real `run()` in
`pyrigor/checkers/cli.py`, and `apply_correction`/`add` as pyrigor's own pervasive example-function names reused across
several real test files. Vulture's unused-detection is name-based, not scope-aware, so it cannot tell those apart from a
fixture's own same-named function — a fragile basis for narrowing, since renaming `cli.py`'s `run()` would silently
start flagging `violations.py`'s own `run()` too, for a reason unrelated to that fixture's own content. Every fixture's
entry point is invoked externally by the pyrigor CLI, never referenced from anywhere else in the corpus, the same
property already established for pyrigor's own self-check exclusion of these files. A real, per-file property confirmed
by isolated testing, not an artefact of scanning them together. Running xenon against the directory found nothing
because trivial one-line fixtures do not trip its complexity threshold, so unlike vulture, no exclusion was needed.
Radon's clean result proved nothing at the time because its hook could not fail. See "Radon's maintainability index is
enforced by a script".

`ty`, `mypy` and `pyright` don't have this problem: confirmed empirically (`mypy .` reports checking exactly 44 source
files, never touching `.venv`), all three have real, built-in smart defaults that skip virtual environments and build
artefacts without any configuration. Vulture's own `--help` says plainly it has none: "For each directory Vulture
analyses all contained `*.py` files."

Fixed by pointing all three at the project (`.`) instead of a hardcoded allowlist, with an explicit, evidence-based
denylist. All three exclude `.venv`, `htmlcov` and `*.egg-info` (never real source). Vulture also excludes
`manual-tests` with `--exclude`, while radon and xenon use `--ignore` for the same patterns. Verified empirically for
each: identical results to before, now covering `scripts/` (radon missed it initially) and `manual-tests/` (all three
missed it) that were previously invisible.

`xenon-shared`'s own single-file list and `tach.toml`'s `[[modules]]` list are deliberately not touched by this — both
are curated by design, not incidental directory discovery. A new file earning a relaxed complexity threshold, or a new
package joining tach's dependency graph, should require a real decision each time, not silently inherit coverage the way
a lint scan should.

### Self-hosted hook version lag is permanent and accepted, not a bug to fix

`.pre-commit-config.yaml`'s self-hosted `jarl-hoyem/pyrigor` hook pin trails the actual released version by one release,
structurally, not just occasionally (#21). The `version_sync.py` only re-syncs pins when a version bump is freshly
staged in `pyproject.toml` — by the time a new tag exists on GitHub (after the release commit is pushed and the release
published), there is no staged bump left to trigger a re-sync. The mechanism cannot close this gap on any later commit.

Considered: a separate, scheduled workflow periodically checking whether the pinned rev matches the latest GitHub
release and opening a PR to bump it, similar in spirit to `pre-commit-autoupdate.yaml` but targeted at this one pin.

Chosen instead: accept the one-release lag as permanent, and document it explicitly where a reader would actually notice
the drift (`.pre-commit-config.yaml`'s own comment), not only in `version_sync.py`'s docstring as before. A dedicated
scheduled workflow is a real, ongoing maintenance surface for a cosmetic gap. The pinned entry's whole purpose is
confirming the released package works the way an external adopter would use it, which it still does correctly one
version behind. Revisit only if a real consumer is ever confused by the lag in practice, not preemptively.

### The pyrigor suppression comment must come last when stacked with another tool's

The regular expression in `_suppressed_tokens()` (`#\s*pyrigor\s*:\s*(?P<tokens>.+)$`) captures everything after
`# pyrigor:` to the end of the line as the reason. Stacking another tool's suppression comment (`# nosec`,
`# complexipy: ignore`) after pyrigor's own gets silently absorbed into that reason text, since `body.partition("#")`
only splits once.

Considered fixing the parser instead, truncating the reason at the next `#` regardless of what follows. Rejected — this
would break a legitimate case: a reason referencing a GitHub issue number, for example `# pyrigor: 406 # see issue #42`.
Truncating trades away real information to guard against a risk that, checked directly, has no current observable
effect. The function `filter_suppressed()` never reads a reason's content, only checks whether it is None.

Chosen instead: a house convention, not a code change. The pyrigor suppression comment goes last when stacked with
another tool's (`# nosec  # pyrigor: PYR402 # reason`, not the reverse). The opposite ordering already works correctly,
since `re.search` finds `# pyrigor:` wherever it appears on the line — this convention costs nothing beyond documenting
it.

### Suppression scanning uses tokenising, not raw-line regular expression

`_suppressed_tokens()` and the near-miss check both used to search each candidate physical line's raw text via regular
expression (`_SUPPRESSION_PATTERN`, `_NEAR_MISS_PATTERN`), with no awareness of Python's lexical structure. A string
literal or docstring whose contents happened to exactly match `# pyrigor: CODE # reason` syntax would not just trigger a
spurious near-miss warning — it could silently suppress a real violation on that line, since regular expression over raw
text cannot tell a genuine comment from text that merely looks like one inside a string. Found scanning `tests/` for the
first time: a near-miss warning fired on a test's own fixture string containing literal `# pyrigor` text, not a real
comment (#41).

Chosen fix: tokenise the source once per every file with Python's own `tokenize` module, and build a
line-number-to-comment-text mapping from genuine `tokenize.COMMENT` tokens only. String and docstring content is
tokenised as `STRING`, never `COMMENT`, so text that only looks like a suppression comment inside a string can no longer
match at all. Candidate-line lookup changed from list-indexing raw source lines to a dict lookup on this map, which also
removes the need for the old `_line_at()`'s explicit out-of-range bounds check — a missing dict key returns "", the same
"no comment here" result an out-of-range line used to require special-casing for.

Rejected: keeping the regular expression approach and trying to special-case strings within it (for example, stripping
string literals from each line before searching). Would need to reimplement a real Python tokeniser piecemeal to handle
multi-line strings, f-strings and escaped quotes correctly — strictly more code and later risk than just using the
tokeniser the standard library already provides for exactly this purpose.

### Suppression syntax drops the colon after "pyrigor" (permanent change)

`# pyrigor: CODE # reason`'s colon collides with ruff's `ERA001` (commented-out-code) when the suppression comment sits
on its own line (the line-above form): `ERA001` only inspects standalone comments, and its actual detection mechanism is
an attempt to parse the comment text as real Python (`parse_module(line).is_ok()`). The `pyrigor: 402` parses
successfully as a bare variable annotation statement (`name: value`), so `ERA001` flags it as commented-out code.
Confirmed directly against a real, installed ruff 0.16.3, not just inferred: `# pyrigor: 402 # reason` on its own line
is flagged. Whereas `# pyrigor 402 # reason` (space instead of colon) is not.

Considered: requesting pyrigor's own comment prefix be added to ruff's `ALLOWLIST_REGEX`, the mechanism `# noqa`,
`# nosec`, `# type: ignore`, and others already use to avoid exactly this collision. Rejected — not contacting ruff's
maintainers to request inclusion, so this is not a path being pursued.

Chosen instead: drop the colon permanently. `# pyrigor CODE[,CODE] # reason`. The regular expression's `\s*:\s*` between
"pyrigor" and the token list becomes `\s+`, requiring only whitespace, not a colon. This is a genuine, permanent syntax
change, not a temporary workaround. Every existing colon-based suppression comment (in this project's own source and in
any external adopters) needs migrating. An un-migrated old comment does not fail silently: `_NEAR_MISS_PATTERN` still
matches it (a colon is not whitespace, so it no longer matches `_SUPPRESSION_PATTERN`, but "pyrigor" is still present),
so it prints the existing near-miss warning rather than suppressing nothing. Closes #46.

## The magic_value pylint extension: Real, independent corroboration of PYR203's boundary

Enabled in pyrigor's own pyproject.toml. Default valid-magic-values (0, -1, 1, "", `"__main__"`) match PYR203's own
chosen exemption list (0, 1, -1) independently. Real corroboration of the boundary is reasonable, not an accident.
Narrower scope than PYR203, though, only fires on comparisons (if x == 3), not arithmetic or function arguments.

Kept running even once PYR203 ships, deliberately, not disabled. The same precedent is already established in this
project: mypy, pyright and ty all run simultaneously despite real overlap in what they catch, genuine defence in depth
from independent implementations, not wasted duplication.

### The tool pylint's check-quote-consistency rejected, real false positives found

Tested empirically against pyrigor's own real source: two "findings", both false positives, single quotes nested inside
a double-quoted f-string's expression (`f"pyrigor {version('pyrigor')}"`, `f"...{', '.join(...)}"`), required on this
project's own supported minimum Python (3.11, pre-PEP 701, cannot nest the same quote character inside an f-string's
expression). The `ruff-format` already correctly, intelligently leaves these alone, quote-nesting-aware. Enabling this
setting would actively fight correct, necessary code, not just duplicate `ruff-format`. Rejected, not enabled.

### The tool pylint's 'allow-global-unused-variables' rejected, real false positives found

Initial testing was flawed, tested only under the setting's own default (true, permissive), never actually verified the
flipped value. Once genuinely set to false: flags every module-level function as an "unused variable" unless it is
called within its own defining file, exactly the wrong behaviour for this codebase, which is built on small,
individually importable, individually testable functions (find_violations, walk_once, count_parameters and every other
checker function). Rejected, not enabled.

## The tool pyrigor's own suppression works anywhere in a wrapped statement's span, deliberately

Confirmed the contrast directly tonight: suppressing ruff's S607/S603 findings on wrapped `subprocess.run(...)` calls
required getting the `# noqa` onto the _exact_ physical line ruff's own diagnostic pointed to, sometimes the opening
line, sometimes the arguments line, easy to get wrong (happened twice in one session). Same friction hit earlier with
the tool bandit's own `# nosec`, same-line only, no tolerance at all.

The tool pyrigor's own suppression mechanism, by design, does not have this fragility. A `# pyrigor CODE # reason`
comment works on the line above the violation, or on any line within the violation's own `end_line` span, not just one
exact physical line. Confirmed by, `test_suppression_comment_on_middle_line_of_multiline_statement_suppresses`. And
confirmed by `test_suppression_comment_on_closing_line_of_multiline_statement_suppresses`.

Worth stating this explicitly as a real, deliberate design advantage in the README.md or the eventual suppression-syntax
reference doc, not just an implicit property. Adopters coming from the ruff/bandit's own stricter placement rules will
likely appreciate knowing this up front.

## The tool ruff's select = ["ALL"] adopted, with a real, evidence-based ignore list

Considered simply picking a curated set of categories versus enabling everything and reviewing what comes back. Chose
"ALL" plus a deliberate ignore list, following Pickomino's own real precedent (confirmed directly from its
pyproject.toml), rather than guessing at categories in the abstract. Every ignored rule has a real, specific reason
(D203/D213/D413 conflict with the chosen docstring convention, COM812 conflicts with the formatter, EM101/EM102/TRY003
reflect this project's own no-custom-exception-hierarchy style, CPY001 has no adopted copyright convention). Verified
empirically at each step (427 findings raw, resolved category by category down to 16 real, individually reviewed fixes)
rather than trusting the ignore list's own reasoning without checking real output.

## Dev-tooling scripts share real logic via a `check: bool` parameter, not a hardcoded default

The file check_definition_of_done.py and version_sync.py both needed the identical git-diff-inspection logic
(staged_files, pyproject_version_changed), found as genuine duplicate code by pylint's own R0801, not just an incidental
shared literal (unlike the filename-constants decision, which stayed local per script). Extracted into
scripts/dev_tooling_shared.py.

The two callers need genuinely different failure behaviour, though: check_definition_of_done.py explicitly promises
"never fails the commit" in its own docstring, so a real git failure should not crash it (check=False). The file
version_sync.py makes no such promise and already has a real, intentional failure path (sys.exit(1)), so a real git
failure surfacing (check=True) is more honest than silently continuing with empty data. Rather than hardcode one
behaviour into the shared functions, check is a required keyword argument, letting each caller express its own actual
philosophy.

### Branch protection on main was verified via a real test pull request

This was not just the API response.

#19 added branch protection (13 required checks from `ci.yaml`, 1 required review, strict mode) via a direct `gh api`
call. The API response confirmed the settings were accepted. But that only proves GitHub stored the configuration, not
that it behaves as intended — this repo had zero human-authored PRs before this point (all five prior PRs were
Dependabot's), so the mechanism had never actually been exercised.

Verified directly, this very entry is the content of that test PR:

- All 13 required checks ran and passed. `mergeStateStatus` stayed `BLOCKED` and `reviewDecision` stayed
  `REVIEW_REQUIRED` anyway — green checks alone do not satisfy the review requirement, the two gates are genuinely
  independent.
- A wrong assumption caught in the process: self-approval is not an org-only restriction. GitHub blocks a PR's own
  author from approving it as a baseline rule — confirmed directly, the author hit this in the real GitHub UI, not
  inferred from documentation. Exactly which review-related settings _are_ org-specific (versus this universal one) was
  not re-verified and should not be assumed either way without checking again.
- Practical consequence for a solo maintainer: `enforce_admins: false` is what actually makes merging your own PR
  possible at all right now, via the "merge without waiting for requirements" administrator-bypass path, not by
  approving your own work. #56 (move to an org once a second contributor exists) still stands, corrected to reflect
  this. The real gap is not "self-approval is allowed," it is "the only way to merge solo is an administrator override
  that skips the review gate entirely."

### `ruff format` adopted over `black`, confirmed empirically not assumed

Real comparison run against this project's own source (`pyrigor/`, `scripts/`, `tests/`), not assumed from either tool's
reputation: `black --check --diff` (matching `line-length = 120`) found exactly one real disagreement — a blank line
`black` wants inserted after a module docstring immediately followed by a comment. Fourteen files, always the same
single-line pattern, nothing else. Output is otherwise identical.

Timing on the same run: `ruff format --check` finished in 0.24 s, `black --check --fast` in 4.43 s — 18x, though at this
codebase's small size that gap is dominated by `black`'s own Python-interpreter startup cost, not necessarily per-file
work. The direction (ruff, written in Rust, faster) is real and expected, the exact multiple is not a claim about the
scale.

Chosen for both reasons together, not either alone: near-identical output removes any real formatting-preference cost to
switching, and `ruff` is already a required dependency for linting (`select = ["ALL"]`) — `ruff format` adds zero new
tools or config surfaces, where `black` would be a second, separate tool doing overlapping work.

Real history behind this, not just the comparison above: `black` and `ruff` fighting circularly, each run undoing the
other's formatting choice, was a genuine, repeated problem before `ruff format` replaced `black` outright, with smaller
versions of the same fight against `isort` too. It traces back further than this project: the same shape of conflict,
PyCharm's own built-in formatter against `black`, is where this whole line of tool-configuration discipline actually
started, in Pickomino (see the "Pickomino inheritance audit" milestone) — `black` won that round. The tool `ruff` won
the next one. Consolidating onto one tool per job, instead of layering several with overlapping opinions, came from
living through both, not from reading about either.

### xenon's two-tier grade system

The tool xenon has no per-function suppression mechanism, unlike complexipy's inline `# complexipy: ignore`. The
`xenon-shared` hook (relaxed to grade B) exists specifically for files with a documented, real exception (currently
`_shared.py`'s `walk_once`, see the 'ast.walk' entry above), while the default `xenon` hook stays at strict grade A for
everything else. A file only qualifies for the relaxed hook once it has its own DECISIONS.md-documented reason, not by
default.

### The tool vulture's confidence threshold

Kept at its default (60), deliberately, not tuned. Real runs against pyrigor/, scripts/, tests/ and manual-tests/
produced zero false positives at this threshold, no evidence raising it would help, and raising it risks missing genuine
dead code. (Per-file isolation testing of the manual-test fixtures revealed real unused findings in five of six files.
They only appeared "used" in whole-directory scans because of name collisions with real code elsewhere, a fragile basis
for any narrowing.)

### `tach` adopted for module-boundary enforcement, real boundaries from real architecture

`tach check` ran clean, zero findings, against a `tach.toml` marking every individual `pyrXXX_*.py` checker as its own
isolated module (never importing another checker, only `_shared.py`/`rules.py`/`violations.py`), `_shared.py` and
`cli.py` each as their own module, and `scripts/`/`tests/` each as one coarse module separate from the real package. The
clean result confirms these boundaries were already followed informally. Adopted despite finding nothing today, for its
preventive value against a future accidental import, matching this project's own stated philosophy (README.md: "Do not
rely on convention or code review where a tool can enforce correctness instead") — not because a current violation
demanded it. See #7.

Real, ongoing cost: `tach.toml` needs updating whenever a new `pyrXXX` checker is added, or the new file silently falls
outside `tach check`'s tracking — `ADDING_A_RULE.md`'s own checklist gained a step for this.

### Prettier adopted as the Markdown formatter, and what it does not cover

Markdown formatting was previously discipline. Wrapping was done by hand, which meant it could be noticed but not
checked. This file's own stopping rule says a prose or style rule must be mechanically checkable, or it is only a
preference, and wrapping was the clearest case of a rule nothing could decide.

Configuration, in `.prettierrc.json`: `proseWrap: "always"`, `printWidth: 120`, `endOfLine: "lf"`, applied to `.md`
only, through a pre-commit hook. Its version lives in `package.json` and `package-lock.json`, as recorded in "Prettier
runs from the locked package, with one pin".

Each value earns its place. The default, `proseWrap: "preserve"`, leaves existing wrapping untouched and therefore
enforces nothing, so `"always"` is what makes the rule mechanical rather than advisory. Width 120 is not a new number:
markdownlint's MD013 and ruff's line-length already use it, so one figure now governs prose, Markdown structure and
Python alike. LF matches `.gitattributes`.

The real cost is not hypothetical. The `guidelines/RULES.md` is generated by `scripts/generate_rule_table.py`, and the
generator had to be changed to emit Prettier-compatible output. Without that, the generator and the formatter rewrite
each other's work on every commit. This is the same fight recorded above between `black`, `ruff format` and `isort`,
arriving in a new place: a code generator against a formatter, rather than two formatters. Any future generator that
writes Markdown inherits the same constraint.

What Prettier does not do is worth stating, because a formatter invites the assumption that prose is now handled. It
reflows text. It does not touch apostrophes (#218), em and en dashes (#219), spelling or contractions (#221) or heading
case (#233). Those four remain open work, and #234 tracks the checks for the two of them that nothing enforces yet.

The same configuration was copied to the `spikes` repository, so both repositories format Markdown identically.

### Whole-project tools take their exclusions from `.gitignore`

Six tools scan the whole project rather than the files pre-commit passes them: mypy, ty, pyright, radon, xenon and
vulture. Each carried its own list of generated and vendored directories to skip. The lists had drifted apart. A
leftover `mutants/` directory from mutation testing showed the cost. Both `mypy .` and `radon mi .` reported files from
inside it, reproduced before this change. See #215.

The `.gitignore` file already names every generated and vendored directory, so it is the single source of truth. The ty
checker respects it by default. The mypy checker reads `exclude_gitignore = true` from `pyproject.toml`, so the hook and
`just mypy` share one setting. The tools radon, xenon, vulture and pyright cannot read `.gitignore`. Their hooks run
through `scripts/run_on_git_python_files.py`, which passes them the Python files listed by
`git ls-files --cached --others --exclude-standard`. No tool keeps its own list of generated directories. A new
generated directory needs only a `.gitignore` entry, and a new source directory is checked as soon as it exists, tracked
or not.

The pre-commit framework could not supply this on its own. On a normal commit it passes only staged files to a hook, and
its top-level `exclude:` filters only the filenames it passes. Hooks that need whole-project results, such as vulture's
unused-code detection and xenon's averages, run with `pass_filenames: false`, so neither mechanism reaches them.

The first version kept a literal list per tool and added a check that failed when the lists drifted apart. That made
drift loud but kept four copies. The wrapper replaced it within the same issue.

Two deliberate exclusions remain because they are design choices rather than generated directories. The vulture hook
excludes `manual-tests`. The strict xenon hook excludes `pyrigor/checkers/_shared.py`, which `xenon-shared` checks at a
relaxed grade. That glob used to be `*_shared.py`, which also hid `scripts/_dev_tooling_shared.py` and
`tests/checkers/test_shared.py` from both xenon hooks. It now names the one intended path.

A manual pyright run ignores `.gitignore` unless it goes through the wrapper, as `just pyright` and `AGENTS.md` now do.

Facts about the repository, such as its well-known filenames, and logic several scripts need live in
`scripts/dev_tooling_shared.py`. Data only meaningful to one script stays in that script. The module lost its leading
underscore within the same issue. Nothing depended on the underscore, and removing it deleted two `import-private-name`
suppressions instead of adding three more.

### Radon's maintainability index is enforced by a script

Radon has been one of three complexity tools since the first tooling commit, alongside xenon and complexipy. It measures
something the other two do not: the maintainability index, which falls mainly with module size and Halstead volume.
Xenon grades cyclomatic complexity and complexipy grades cognitive complexity per function, so neither is designed to
catch a long module of simple functions.

Its hook could never fail. The `radon mi` command has no failing exit status, and `--min A` only filters what it prints.
A probe module scoring 0.00, rank C, exited 0 with the hook's own arguments and pre-commit hides a passing hook's
output. Two test modules had fallen below A unnoticed: `tests/checkers/test_cli.py` at C and
`tests/checkers/test_pyr406_return_values_used.py` at B.

The hook now runs `scripts/check_maintainability.py` through the git file-list wrapper. The script runs
`radon mi --json` and fails on any rank below A, on a file radon cannot parse and on a radon crash. It runs radon as a
subprocess rather than importing it, because radon ships no type information, and strict mypy and pyright would need a
stub or suppressions.

The two test modules are listed with `--allow`, the same kind of documented exception as the file `xenon-shared`
relaxes. An entry fails once its module ranks A or is no longer checked, so an exception cannot outlive its split. Both
are tracked by #268, which is blocked by #225.

### Python tool versions live in pyproject.toml, and pre-commit only runs the tools

The ruff version was stated twice, as a dev-extras floor and as the hook's `rev:` pin, and the two had drifted before.
The same problem existed elsewhere. Radon was pinned in the dev extras and again in its hook's
`additional_dependencies`. Xenon and tach were pinned only in `additional_dependencies`. The pip-audit hooks used
`uv run --with pip-audit`, so pip-audit was pinned nowhere and took the newest release on every run. See #248.

Issue #248 recommended removing ruff from the dev extras and keeping the `rev:` pin. Before following it, the IDEs were
checked for a dependency on the dev-extras ruff. PyCharm 2025.2 has no native ruff integration. The Docker inspection
runner's PyCharm has one, which is why `.idea/pyLspTools.xml` exists, but its container never installs the project's
dependencies. Nothing relied on the dev-extras ruff.

That option would still have split tool versions across two files. Moving every Python tool into the dev extras puts
each version in one place: a floor in `pyproject.toml` and an exact pin in `uv.lock`. A local hook's entry names the
tool but carries no version. Only tools that are not Python packages keep a `rev:` pin: gitleaks, actionlint and
markdownlint-cli2. Prettier, a Node package, is pinned in `package.json` and `package-lock.json`. The published pyrigor
hook also keeps its pin because it deliberately tests the released hook.

The move was checked before it was made. All eleven tools resolve together with the existing dev extras for Python 3.11
and later. Wheels exist for every tool on Python 3.11 to 3.14 on Linux, Windows and macOS. The 3.15 prerelease builds
`pyyaml` from source everywhere, and `complexipy` on Windows and macOS, which CI already did inside the hook
environments.

The costs were accepted knowingly. Each converted hook repeats its upstream name, file types, arguments and whether it
runs serially. Pre-commit's isolated environments are gone, so a dependency conflict between tools now surfaces in
`uv lock`. The lock grew from 52 to 97 packages. The `pre-commit autoupdate` workflow no longer updates these tools, so
Dependabot's `uv` ecosystem now proposes monthly updates for every dev extra.

The floors first resolved to newer commitizen, tach and complexipy releases, including complexipy 8, a major version.
The lock was set back to the previously pinned versions, so the move changed no behaviour. Those upgrades arrive as
separate Dependabot pull requests. The same 41 hooks run with the same results before and after, apart from the hook id
`ruff` becoming `ruff-check`, and a deliberate violation still fails each converted hook.

The mutmut Docker image had the same gap. It ran `pip install`, which took the newest release of every dev tool, so CI
ran mutmut 3.8.0 while the lock pinned 3.7.0. The newer mutmut created 42 more mutants, so the mutation score changed
with upstream releases rather than with pyrigor. The image now runs `uv sync --locked`, and Dependabot's `docker`
ecosystem updates its uv image pin.

### The two slowest checks run on push, not on every commit

Measured on 2026-09-18: a commit touching one Python file cost 34 seconds, and a Markdown-only commit 25 seconds. The
suite pays about 2 seconds of startup per hook, and pytest at 15 seconds and the local pip-audit at 3 seconds sat on top
of that. Moving both to the `pre-push` stage brought the same commits to 17 and 11 seconds.

Nothing reaches a branch without them. Pre-commit's pre-push hook runs both before a push, and CI runs the pre-commit,
pre-push and manual stages, so the workflow file still mirrors the hook file. The audited environment cannot change
between commits unless the lock changes, and that change is itself committed and audited on the next push.

The cost is that one commit in a series can contain failing tests. That is accepted because the series is not shared
until it is pushed, and bisecting over a local commit is rare compared with the time a full suite takes on every commit.
Parallel runs of the remaining checks are a separate question (#199), and the measurements above are recorded there.

### Prettier runs from the locked package, with one pin

Prettier's version was stated twice. The first place was `package.json` and `package-lock.json`, which PyCharm's
format-on-save uses. The second was the hook's `additional_dependencies`, which let CI run the hook without installing
Node. A script, its test and the `prettier-pin-sync` hook existed only to keep the two equal. Nothing updated Prettier
either, because `pre-commit autoupdate` ignores `additional_dependencies` and Dependabot did not watch npm.

The hook now runs `node node_modules/prettier/bin/prettier.cjs` from the locked package, so the lock is the only pin.
The check, its test and its hook are gone. CI's build job runs `npm ci`, `just setup` runs `npm ci` instead of
`npm install` and Dependabot's `npm` ecosystem proposes Prettier updates. This follows the rule already chosen for the
Python tools: a version lives in the tool's own manifest and lock, and pre-commit only runs the tool.

The entry calls the package's binary directly rather than through `npx`. A first version used `npx --no -- prettier`,
which fell back to globally installed Prettier when `node_modules` was missing. The hook then passed with whatever
version happened to be installed globally, which would silently undo the single pin. The direct path fails with
`Cannot find module` instead.

The cost is that CI needs Node, which GitHub's hosted runners already provide, and a fresh clone needs `just setup`
before committing. Contributors already needed Node for the IDE, so only CI gained a step.

Removing the check left `version_sync.py` as the only script using `PRE_COMMIT_CONFIG`. The earlier rule kept a constant
shared only while several scripts used it. So the constant would have moved back into that script after moving out the
day before. The rule now asks what a constant is rather than how many scripts use it: facts about the repository stay
shared, and data only meaningful to one script stays local.

### The tach pytest plugin is disabled, and every CI job has a time limit

Moving tach into the dev extras (#248) loaded its pytest plugin, `tach.pytest_plugin`, into every pytest run. The plugin
registers itself through a `pytest11` entry point, so installing tach is enough to activate it. Whenever a `tach.toml`
exists, it runs git commands and builds a Rust handler during pytest startup, even without `--tach`. Before the move,
tach lived only in its isolated pre-commit environment, where pytest never saw it.

Under mutmut, every mutant then timed out. The CI mutation-test job normally takes about two minutes, but it hung until
cancelled, on every commit from the move onwards. Reproducing the step with the CI image showed the cause directly. Run
as CI runs it, all 205 mutants reached before a 10-minute limit had timed out. With `PYTEST_ADDOPTS=-p no:tach`, all
1,594 mutants completed in 221 seconds. The most likely mechanism is mutmut forking its worker processes after the
plugin's Rust code has started threads, but that was not proven, and the fix does not depend on it.

The project never uses tach's test selection, so the plugin only added git calls to every run. It is disabled with
`-p no:tach` in pytest's `addopts` in `pyproject.toml`, which covers mutmut, the pytest hook `just test` and CI in one
place. Removing that option brings the hang back.

This is a concrete cost of the shared dev environment. A package installed there can change pytest's behaviour through
its entry points, which the isolated pre-commit environments used to prevent. When adding a dev extra, check the plugins
listed by `pytest --version --version`.

The hang did more damage than a failed job would have, because the job had no time limit. GitHub's default is six hours,
so each stuck run held a runner, and newer runs queued behind them until 35 runs were cancelled by hand. Every job in
every workflow now sets `timeout-minutes`. Each limit is at least five times the longest run observed, and never under
10 minutes, so an ordinary slow day does not fail a healthy run. Three jobs get more room: the build matrix gets 35
minutes, because a cold Python 3.15 build compiles `complexipy` from source on Windows and macOS. The large-repository
smoke test gets 20 because it clones Home Assistant over the network. The mutation test gets 15. A limit that proves too
tight costs a rerun, while no limit cost hours of blocked CI.

### PYR402 fixer: the `end` bound and its fallbacks were dead weight, not defensive code

#308 found the `< 0` guards, the `end` bound on both `find` calls and `node.end_col_offset or 0` /
`end_lineno or lineno` fallbacks in `pyr402_keyword_only_arguments_fixer.py` all survived mutation testing. Rewriting
`< 0` as `== -1` now fails the project's own ordinary tests when mutated, not only the two str-subclass doubles built
for that guard.

The `end` bound was never load-bearing: `node.lineno`/`col_offset` always land on the `def`/`async` keyword past any
decorator, so nothing but the function's own name sits between `start` and its opening parenthesis, and the comma search
only runs once `_MINIMUM_POSITIONAL_PARAMETERS` has already guaranteed a real separating comma. Verified against an
adversarial multi-function file with no cross-function contamination. With the bound gone, `end_byte`/`end_column`/
`end_line` had no remaining use, so they were deleted along with their `or 0` fallbacks, rather than defended with an
`assert`. `end_col_offset`/`end_lineno` are in fact never `None` for a parsed node, but removing the code that needed
the fallback was the simpler fix than proving it unreachable.

### Pylint's duplicate-code check needs `require_serial`

`just check` passed cleanly on the split of `test_pyr406_return_values_used.py` into two files, then the same content
failed `pylint`'s `R0801` (duplicate-code) at actual commit time. Confirmed directly: plain `pylint` on the two files,
with or without the rest of the corpus present, finds the same four instances every time. Only pre-commit's own
invocation is inconsistent.

`pre_commit/lang_base.py`'s `run_xargs()` shuffles `file_args` and splits them across one subprocess per CPU core unless
a hook sets `require_serial: true`. The `R0801` can only see duplication between files given to the same pylint process.
`just check`'s `--all-files` run passes the whole tracked Python file list, large enough to span several parallel
batches, so the two files landed in different processes and neither saw the other. A real commit passes only the files
that changed, few enough to land in one batch, so `R0801` fired correctly there and only there.

The pylint hook now sets `require_serial: true`, trading `just check`'s own parallelism for `R0801` actually working
under `--all-files`. The alternative, leaving it parallel and trusting commit-time runs to catch what `just check`
misses, defeats the entire point of running `just check` before committing.

### #311: two more unreachable fallbacks, same shape as #307/#308

`_latest_binding`'s `getattr(node, "lineno", 0)` defaults and `nearest_function_scope`'s `else node` base case were both
confirmed unreachable the same way: mutate the fallback, run the full suite, nothing fails. Both are now explicit
`raise ValueError(...)`, matching `pyrigor/violations.py`'s own precedent, with `_binding_position` (a `NamedTuple`, not
a bare tuple, per PYR401 on pyrigor's own source) carrying the guard instead of `_latest_binding` itself.
