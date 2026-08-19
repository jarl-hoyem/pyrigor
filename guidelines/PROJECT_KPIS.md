# Project KPIs

Lightweight, low-effort metrics tracked at release time to catch
regressions the test suite can't see: a rule quietly becoming too
noisy on real-world code, not just correct on pyrigor's own
fixtures. `PERFORMANCE.md` already does this pattern for speed; this
is the same idea for false-positive rate.

Kept to one metric until a real gap shows up that this one doesn't
catch — the same discipline `REVIEW_CHECKLIST.md` applies to its own
questions.

## Real-world violation count per release

**What:** run pyrigor against a large, real-world, non-pyrigor
codebase and record the violation count, broken down per rule.
Compared release-over-release, a rule whose count jumps sharply
without a matching rule change is a signal worth investigating —
either the rule got broader than intended, or the corpus itself
changed underneath it (see "Pin refreshes," below).

**Corpus:** [home-assistant/core](https://github.com/home-assistant/core),
pinned to a fixed commit so release-over-release deltas are
comparable. The pin is deliberately NOT bumped on every release —
only on a deliberate, noted refresh — otherwise a count change could
come from home-assistant's own code changing instead of pyrigor's.

**When:** once per release, as part of the release checklist in
`DEFINITION_OF_DONE.md`.

**How:**

```bash
git clone --depth 1 --branch <pinned-tag-or-commit> https://github.com/home-assistant/core /tmp/ha-core
uv run pyrigor /tmp/ha-core > /tmp/kpi-run.txt
```

Record the per-rule breakdown from the summary output below.

## History

| Release | Corpus pin | Files | Total violations | Per-rule breakdown | Delta vs. prior |
|---|---|---|---|---|---|
| _(first row populated at the next release)_ | | | | | |

## Pin refreshes

Log here whenever the corpus pin is deliberately bumped, and why —
so a future reader doesn't mistake "home-assistant added new code"
for "pyrigor got noisier."

- _(none yet)_
