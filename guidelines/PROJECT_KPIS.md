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

Keep one local checkout outside this repository and reuse it for each
release. The checkout is not part of the project and must not be committed.
Before each run, check out the pin recorded in the table:

```bash
git -C <persistent-ha-core-checkout> checkout --detach <pinned-tag-or-commit>
uv run pyrigor <persistent-ha-core-checkout> > /tmp/kpi-run.txt
```

Fetch or clone the checkout only when establishing it or deliberately
refreshing the corpus pin. Record any deliberate refresh in the
**Pin refreshes** section below.

Record the per-rule breakdown from the summary output below.

### History

| Release | Corpus pin                       | Files | Total violations | Delta vs. prior           |
|---------|----------------------------------|-------|------------------|---------------------------|
| 0.7.4   | home-assistant/core @ `ac63da9`  | 18221 | 90921            | _(first row)_             |
| 0.8.0   | _(skipped, see note below)_      |       |                  |                           |
| 0.9.0   | home-assistant/core @ `ac63da9`  | 18223 | 90927            | +2/+6 vs 0.7.4 (see note) |
| 0.10.0  | home-assistant/core @ `80fd0c5f` | 18187 | 90501            | -36/-426 vs 0.9.0         |
| 0.11.0  | home-assistant/core @ `80fd0c5f` | 18187 | 90501            | 0/0 vs 0.10.0             |

**Per-rule breakdown:**

| Release | PYR301 | PYR401 | PYR402 | PYR403 | PYR405 | PYR406 |
|---------|--------|--------|--------|--------|--------|--------|
| 0.7.4   | 55     | 585    | 58819  | 30861  | 425    | 176    |
| 0.9.0   | 55     | 585    | 58821  | 30865  | 425    | 176    |
| 0.10.0  | 55     | 579    | 58485  | 30786  | 420    | 176    |
| 0.11.0  | 55     | 579    | 58485  | 30786  | 420    | 176    |

0.8.0 was skipped deliberately: neither #11 nor #46 changes what
pyrigor detects (label text and suppression-comment recognition
only), so a rescan would reproduce 0.7.4's row unchanged.

0.9.0's tiny +2 file / +6 violation difference from 0.7.4, despite
the identical corpus pin and no detection-logic changes since, is
most likely a minor extraction-method difference (a GitHub archive
tarball this time, versus a `git clone` originally), not a real
corpus or rule-behavior change.

### Pin refreshes

Log here whenever the corpus pin is deliberately bumped, and why —
so a future reader does not mistake "home-assistant added new code"
for "pyrigor got noisier."

- _(none yet)_
- 0.10.0 uses `80fd0c5f` because the previous `ac63da9` pin is no
  longer available from the Home Assistant repository.

## Code-quality statistics (% comments, % blank) per release

**What:** run `radon raw` against pyrigor’s own source and record
its line-count fields — `loc` (Lines of Code, every physical line),
`lloc` (Logical Lines of Code, one count per logical statement,
insensitive to line-wrapping or formatting choices), `sloc` (Source
Lines of Code, physical lines that are neither blank nor a
comment-only line), comments, multi-line string lines, single-line
comment-or-docstring lines, blank — plus a derived comment ratio.
Note: radon does not cleanly separate
comments from docstrings — `single_comments` covers both standalone
comments and one-line docstrings, and `multi` is multi-line string
content, not docstrings specifically. Observational only
for now — no minimum ratio is enforced. If the
trend shows something worth acting on later, that becomes its own,
separately decided rule or hook, not an automatic consequence of
adding this table.

**Which to judge by:** `lloc` is the best signal for whether the
code itself grew, since it is not affected by added blank lines,
reformatting, or wrapped long lines the way `loc` and `sloc` are.
Watch it against the comment ratio below — `lloc` growing while
comments do not keep pace is the real erosion signal this table
exists to catch, distinct from `loc`/`sloc` movement caused by pure
reformatting.

**Comparing against another project:** that guidance is for
pyrigor’s own releases, measured with the same tool — comparing
pyrigor’s size to a different project (a README claim, a GitHub
language-stats page) is a different question. The `sloc` is the
conventional choice there: it is what most external tools report by
default (`cloc`, GitHub’s own stats) and what classic
cost-estimation models like COCOMO are built on, so it is the only
one of the three likely to be measuring the same thing as whatever
number the other project published. The `lloc` is formatting-insensitive
and arguably the more honest size measure, but almost nothing
outside Python tooling reports it, so it only works when both
projects are measured with the same tool. Plain `loc` is the weakest
choice either way, most sensitive to superficial style (blank-line
density, comment volume) rather than real size.

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
comment ratio (`comments / sloc`) below.

### History

| Release | Files | LOC  | LLOC | SLOC | Comments | Multi | Single-line | Blank | Comment ratio | Delta vs. prior |
|---------|-------|------|------|------|----------|-------|-------------|-------|---------------|-----------------|
| 0.7.4   | 13    | 1469 | 583  | 547  | 22       | 499   | 39          | 384   | 4.0%          | _(first row)_   |
| 0.8.0   | 13    | 1483 | 588  | 558  | 22       | 501   | 39          | 385   | 3.9%          | _(see note)_    |
| 0.9.0   | 13    | 1605 | 632  | 628  | 23       | 532   | 41          | 404   | 3.7%          | _(see note)_    |
| 0.10.0  | 13    | 1811 | 736  | 778  | 23       | 539   | 54          | 440   | 3.0%          | -0.7 pp         |
| 0.11.0  | 13    | 1855 | 747  | 812  | 23       | 543   | 56          | 444   | 2.8%          | -0.2 pp         |
