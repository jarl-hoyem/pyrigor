# Review checklist

A Fagan-Inspection-style checklist, in the sense of Gilb and Graham’s
*Software Inspection*: checklist questions derive their authority
from a rule, are earned one at a time by a real defect that slipped
through, and are pruned if they stop finding anything. Not
brainstormed, not copied from elsewhere.

Format: each question is phrased, so a **no** answer means an issue
was found. Each question tags back to the rule it elaborates.

Run this checklist before declaring any feature, flag, or fix done,
alongside `DEFINITION_OF_DONE.md`.

## Questions

1. **Is every behavior explicitly claimed for this feature backed by
   its own test, checked individually, not inferred from the suite
   passing overall?**
   ← rule: `DEFINITION_OF_DONE.md`, Correctness
   *Earned by:* `--only` was scoped as "same lenient forms as
   suppression comments" and shipped with tests for code-form and
   symbolic-name-form only. Whitespace tolerance, something
   suppression comments already had a dedicated test for, was never
   checked. Caught by the user asking a follow-up question, not by
   any process then.

2. **Did this change involve a real architectural or design decision?
   If so, has `DECISIONS.md` been checked and updated by name, not
   just README.md and CHANGELOG.md?**
   ← rule: `DEFINITION_OF_DONE.md`, Communication
   *Earned by:* the ast.walk refactor's own design decision, the
   shared-walk approach and the rejected cache-based alternative,
   went undocumented in `DECISIONS.md` until asked about directly.
   `DEFINITION_OF_DONE.md`'s "any relevant guidelines/ doc" wording
   was too vague to catch it, only the explicitly named README.md
   and CHANGELOG.md got checked in practice.

## Retroactive applications

- **2026-08-16**: Question 1 applied retroactively across prior
  work (PYR401, PYR403, suppression: out-of-range line guard,
  --only’s two known gaps). Found: PYR401 and PYR403 both lacked an
  async-function test (added, both passed, confirming existing code
  was already correct). Suppression’s defensive out-of-range guard
  had never been tested (added, confirmed correct). --only’s
  unknown-code behavior was genuinely undefined (fixed separately,
  not just tested). No new checklist question earned: this was
  question 1 doing its job on prior work, not a new failure mode.

## Adding a question

A question is only added here after a real defect slipped through
that this checklist, if it had existed with that question already on
it, would have caught. When adding a question, log the defect it was
caused by, and note that this same question would have caught it,
the same way each entry above does.

Do not add a question because it seems like good practice in the
abstract. That produces exactly the "obvious or irrelevant" checklist
*Software Inspection* warns against, one looking thorough but
does not find anything, because it was never tied to a real
failure.

## Removing a question

If a question has not caught anything over a reasonable period,
across enough real feature work to have had a chance to remove it.
An unused question makes the checklist longer without making it more
effective and erodes trust in the ones that do work.
