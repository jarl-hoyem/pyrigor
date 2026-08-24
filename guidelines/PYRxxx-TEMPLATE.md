# PYRxxx — <Short, mandate-stated title (see NAMING.md)>

## Rule

<State the mandated pattern in one or two sentences. Show a minimal
Bad/Good code pair.>

```python
# Bad
...

# Good
...
```

## Rationale

<Explain *why* the rule exists: the specific defect class it
prevents, with a concrete example of the bug slipping past whatever
tools already run (ruff, mypy, pytest, ...). Engage directly with
any real, considered alternative (a competing style guide's own
recommendation, a documented trade-off) rather than ignoring it —
see PYR401's "A note on Google's Python Style Guide" section for the
precedent.>

## Fix classification

<Added following #105's real, per-rule classification (see
DECISIONS.md for the adoption decision this template implements).
Every rule declares which of three tiers its violation belongs to —
this is a real design decision, not a formality, and directly
informs whether/how an eventual `suggest()` implementation would
handle it.>

**Kind:** `safe_fix` | `suggestion` | `guidance`

- **`safe_fix`** — the transformation is mechanically, unconditionally
  correct. Any consequence of the change at a call site is immediate and loud (a
  type-checker error, not a silent behavior change), not something
  the fix itself could get wrong. Example: PYR402/PYR403 inserting
  `*,` — mechanical, and any resulting caller breakage is caught
  immediately by mypy/pyright, not hidden.
- **`suggestion`** — the tool has a strong, plausible recommendation
  but cannot guarantee it is the *correct* one. A human must confirm
  the design choice (naming, semantic intent) before it is applied.
  Example: PYR201 recommending a specific `NewType` name — a
  reasonable guess, not a guaranteed-correct one.
- **`guidance`** — the tool can identify the concern but cannot
  construct any specific answer at all. The right fix depends
  entirely on the domain/design knowledge the tool has no way to infer.
  Example: PYR301/401/405 (needs invented `NamedTuple`/field names),
  PYR406/407 (the correct handling of a discarded value depends
  entirely on developer intent).

**Reasoning:** <Why this rule sits in this tier specifically — what
would have to be true for it to move to a stricter tier, if
anything.>

## Severity

<Added following #158's real, per-rule severity assignment (see
DECISIONS.md's "Severity" entry for the adoption decision this
template implements). Graded by consequence severity if the
underlying pattern's bug actually occurs, not by how likely that is
— a rule catching a rare but catastrophic bug outranks one catching
a common but low-stakes one. Uses the Language Server Protocol's own
`DiagnosticSeverity` naming, not an invented pyrigor-specific term.>

**Level:** `error` | `warning` | `info`

- **`error`** — the pattern this rule catches is a real, confirmed
  correctness or security bug class, often severe or hard to detect.
  Example: PYR503 (Zip Slip, an actual vulnerability class), PYR303
  (silently skipped elements — real data loss).
- **`warning`** — real defense-in-depth against a swap/misuse risk,
  but narrower blast radius or partially caught by other means
  (mypy, tests). Example: PYR402/PYR403 (keyword-only — any caller
  consequence is already caught by mypy/pyright).
- **`info`** — readability/maintainability, not a silent-wrong-output
  risk. Example: PYR203/PYR205 (magic numbers/`Final` constants).

**Reasoning:** <Why this rule sits at this level specifically —
what would have to be true for it to move to a stricter or lighter
tier, if anything.>

## When this does not apply

<List genuine, considered exclusions — a structural exemption, a
well-established convention this rule would otherwise fight, a
scope boundary. Not a place to narrow the rule to avoid
false positives found along the way. Each exclusion should be a real,
justified case.>

## Related

<Cross-reference every rule with real overlap or a shared underlying
concern, in both directions — update the other rule's own `Related`
section too, not just this one. State precisely what gap each
related rule leaves that this one closes, not just "see also" as a catch-all.>

## Enforced by

<If a checker exists: "The `pyrXXX` checker
(`pyrigor/checkers/pyrXXX_<symbolic_name>.py`), wired in as a
pre-commit hook and available via the `pyrigor` CLI (`pip install
pyrigor`, then `pyrigor path/to/file.py`)." If documented but not yet
enforced: state that plainly, do not imply automatic checking that
does not exist.>

## A note on <source>, if applicable <!-- markdownlint-disable-line MD033 -- placeholder, not real HTML -->

<Optional. If an existing citation (McConnell, Google's Style Guide,
OSSF's Secure Coding Guide, a PEP, ...) directly informs or
disagrees with this rule, engage with it directly here — see PYR401
for the precedent. Not every rule doc needs this section. Only add
it when a real, specific source exists.>
