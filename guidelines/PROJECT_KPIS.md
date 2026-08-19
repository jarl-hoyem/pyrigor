# Project KPIs

Lightweight, low-effort metrics tracked at release time to catch
things the test suite cannot see: a rule becoming too noisy
on real-world code, or the codebase’s own documentation discipline
eroding. The `PERFORMANCE.md` already does this pattern for
speed. These are the same idea for other properties.

Kept to the metrics below until a real gap shows up that neither
catches — the same discipline `REVIEW_CHECKLIST.md` applies to its
own questions.

## Real-world violation count per release

**What:** run pyrigor against a large, real-world, non-pyrigor
codebase and record the violation count, broken down per rule.
Compared to 'release-over-release,' a rule whose count jumps
without a matching rule change is a signal worth investigating —
either the rule got broader than intended, or the corpus itself
changed underneath it (see "Pin refreshes," below).

**Corpus:** [home-assistant/core](https://github.com/home-assistant/core),
pinned to a fixed commit so release-over-release deltas are
comparable. The pin is deliberately not bumped on every release —
only on a deliberate, noted refresh — otherwise a count change could
come from home-assistant’s own code changing instead of pyrigor’s.

**When:** once per release, as part of the release checklist in
`DEFINITION_OF_DONE.md`.

**How:**

```bash
git clone --depth 1 --branch <pinned-tag-or-commit> https://github.com/home-assistant/core /tmp/ha-core
uv run pyrigor /tmp/ha-core > /tmp/kpi-run.txt
```

Record the per-rule breakdown from the summary output below.

### History

| Release                                     | Corpus pin | Files | Total violations | Per-rule breakdown | Delta vs. prior |
|---------------------------------------------|------------|-------|------------------|--------------------|-----------------|
| _(first row populated at the next release)_ |            |       |                  |                    |                 |

### Pin refreshes

Log here whenever the corpus pin is deliberately bumped, and why —
so a future reader does not mistake "home-assistant added new code"
for "pyrigor got noisier."

- _(none yet)_

## Code-quality statistics (% comments, % blank) per release

**What:** run `radon raw` against pyrigor’s own source and record
line counts, split by kind (logical lines of code, comments, blank,
docstring), plus a derived comment ratio. Migrated from
`BACKLOG.md`, [#45](https://github.com/jarl-hoyem/pyrigor/issues/45).
Observational only for now — no minimum ratio is enforced. If the
trend shows something worth acting on later, that becomes its own,
separately decided rule or hook, not an automatic consequence of
adding this table.

**Corpus:** pyrigor’s own source (`pyrigor/`) — no pinning question
here, unlike the metric above, since there is nothing to hold
constant except pyrigor’s own code across releases, which is the
entire point.

**When:** once per release, as part of the release checklist in
`DEFINITION_OF_DONE.md`, alongside the metric above.

**How:**

```bash
uv run radon raw --json pyrigor/ > /tmp/kpi-raw.json
```

Record the aggregate totals (summed across files) and the derived
comment ratio (`comments / (loc - blank)`) below.

### History

| Release                                     | LOC | LLOC | Comments | Blank | Docstring lines | Comment ratio | Delta vs. prior |
|---------------------------------------------|-----|------|----------|-------|-----------------|---------------|-----------------|
| _(first row populated at the next release)_ |     |      |          |       |                 |               |                 |
