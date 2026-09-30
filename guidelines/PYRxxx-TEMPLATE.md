# PYRxxx — <Short, mandate-stated title (see NAMING.md)>

## Rule

<State the mandated pattern in one or two sentences. Show a minimal Bad/Good code pair.>

```python
# Bad
...

# Good
...
```

## Rationale

<Explain _why_ the rule exists: the specific defect class it prevents, with a concrete example of the bug slipping past
whatever tools already run (ruff, mypy, pytest, ...). Engage directly with any real, considered alternative (a competing
style guide's own recommendation, a documented trade-off) rather than ignoring it — see PYR401's "A note on Google's
Python Style Guide" section for the precedent.>

## Fix classification

<Added following #105's real, per-rule classification, redefined by #289 (see DECISIONS.md for the adoption decision
this template implements). Two independent questions: whether a fix can be constructed at all, and, if so, whether it
may be applied automatically. Together these directly inform how an eventual `suggest()` implementation would handle
this rule.>

**Fix availability:** `always` | `sometimes` | `none`

- **`always`** — every violation of this rule can be mechanically fixed. Example: PYR402/PYR403 inserting `*,`.
- **`sometimes`** — a fix can be constructed for some violations of this rule but not others, depending on what pyrigor
  can determine about the specific case.
- **`none`** — no fix is ever attempted. The right answer depends on domain/design knowledge the tool has no way to
  infer. Example: PYR301/401/405 (needs an invented `NamedTuple`/field name), PYR406/407 (the correct handling of a
  discarded value depends entirely on developer intent).

**Applicability:** `safe` | `unsafe` | `display` (omit this field when fix availability is `none`)

- **`safe`** — applying the fix does not change runtime behaviour, matching Ruff's own definition of `safe`. A
  consequence a type checker would catch is not enough on its own; pyrigor does not require running one.
- **`unsafe`** — applying the fix can change runtime behaviour or break an existing caller. Example: PYR402/PYR403 — an
  existing positional call becomes a runtime error, not merely a type-checker finding, since pyrigor does not require
  mypy/pyright and `--fix` runs over whole existing codebases. `--fix` applies an unsafe fix only when its rule is
  explicitly named with `--select`.
- **`display`** — pyrigor can construct and show a specific proposed fix (for example, via `--diff`), but never applies
  it automatically, even with explicit `--select`, because the right edit depends on a design judgment `--fix` cannot
  safely make on its own. Example: PYR201 recommending a specific `NewType` name — a reasonable guess, not a
  guaranteed-correct one.

**Reasoning:** <Why this rule has this fix availability and this applicability specifically — what would have to be true
for either to be different.>

## Severity

<Added following #158's real, per-rule severity assignment (see DECISIONS.md's "Severity" entry for the adoption
decision this template implements). Graded by consequence severity if the underlying pattern's bug actually occurs, not
by how likely that is — a rule catching a rare but catastrophic bug outranks one catching a common but low-stakes one.
Uses the Language Server Protocol's own `DiagnosticSeverity` naming, not an invented pyrigor-specific term.>

**Level:** `error` | `warning` | `info`

- **`error`** — the pattern this rule catches is a real, confirmed correctness or security bug class, often severe or
  hard to detect. Example: PYR503 (Zip Slip, an actual vulnerability class), PYR303 (silently skipped elements — real
  data loss).
- **`warning`** — real defence-in-depth against a swap/misuse risk, but narrower blast radius or partially caught by
  other means (mypy, tests). Example: PYR402/PYR403 (keyword-only — any caller consequence is already caught by
  mypy/pyright).
- **`info`** — readability/maintainability, not a silent-wrong-output risk. Example: PYR203/PYR205 (magic
  numbers/`Final` constants).

**Reasoning:** <Why this rule sits at this level specifically — what would have to be true for it to move to a stricter
or lighter tier, if anything.>

## Tier and maturity

<Added following #162's real, two-axis classification (see DECISIONS.md's "Opt-in rule tier" entry for the adoption
decision this template implements). Two independent axes, neither implied by the other.>

**Tier:** `Default` | `Advisory`

- **`Default`** — runs without being selected, the same as every rule today. Catches a silent bug type checkers/standard
  linters miss.
- **`Advisory`** — excluded from the implicit default set, reachable only via explicit `--select=PYRxxx` (or symbolic
  name). A genuine, opinionated preference someone might deliberately want, not a silent-bug detector — for example, a
  real performance concern rather than a correctness one.

**Maturity:** `Stable` | `Preview`

- **`Stable`** — proven through real dogfooding history.
- **`Preview`** — documentation-only for now and has no CLI flag of its own. `Tier` alone controls whether the rule
  runs.

## Rule metadata

The `RuleInfo` entry in `pyrigor/rules.py` is the canonical source for the rule's symbolic name, problem text, severity,
fix availability and applicability. The values declared in this document's `Fix classification`, `Severity`, and
`Tier and maturity` sections must match that entry once the rule is implemented. The documentation-sync test checks this
agreement.

## When this does not apply

<List genuine, considered exclusions — a structural exemption, a well-established convention this rule would otherwise
fight, a scope boundary. Not a place to narrow the rule to avoid false positives found along the way. Each exclusion
should be a real, justified case.>

## Related

<Cross-reference every rule with real overlap or a shared underlying concern, in both directions — update the other
rule's own `Related` section too, not just this one. State precisely what gap each related rule leaves that this one
closes, not just "see also" as a catch-all.>

## Enforced by

<If a checker exists: "The `pyrXXX` checker (`pyrigor/checkers/pyrXXX_<symbolic_name>.py`), wired in as a pre-commit
hook and available via the `pyrigor` CLI (`pip install pyrigor`, then `pyrigor path/to/file.py`)." If documented but not
yet enforced: state that plainly, do not imply automatic checking that does not exist.>

## A note on <source>, if applicable <!-- markdownlint-disable-line MD033 -- placeholder, not real HTML -->

<Optional. If an existing citation (McConnell, Google's Style Guide, OSSF's Secure Coding Guide, a PEP, ...) directly
informs or disagrees with this rule, engage with it directly here — see PYR401 for the precedent. Not every rule doc
needs this section. Only add it when a real, specific source exists.>
