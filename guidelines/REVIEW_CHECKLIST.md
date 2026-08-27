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
   *Earned by:* the 'ast.walk' refactoring’s own design decision, the
   shared-walk approach and the rejected cache-based alternative,
   went undocumented in `DECISIONS.md` until asked about directly.
   `DEFINITION_OF_DONE.md`'s "any relevant guidelines/ doc" wording
   was too vague to catch it, only the explicitly named README.md
   and CHANGELOG.md got checked in practice.

3. **When a fix is validated by a manual command, has it also been
   confirmed against the actual, real invocation the tool uses in
   practice, not just a convenient proxy for it?**
   ← rule: `DEFINITION_OF_DONE.md`, Correctness
   *Earned by:* `bandit`'s `tests/` exemption pattern was fixed and
   confirmed clean via a manual `bandit -r tests/` scan, which
   produces clean, unprefixed relative paths. The fix genuinely did
   not work for how `pre-commit` actually invokes the hook,
   individual file arguments with a leading `.\` prefix on Windows,
   only caught by testing the real invocation directly
   (`pre-commit run bandit --files ...`), not the manual scan that
   had already been trusted as enough.

4. **When reviewing a comparison source fetched in one pass,
   was every distinct section actually
   individually evaluated, not just the one that produced the most
   obvious finding?**
   ← rule: `DEFINITION_OF_DONE.md`, Correctness
   *Earned by:* Pickomino's `[tool.pylint.variables]` and
   `[tool.pylint.string]` sections were fetched and displayed in
   full during the same pass that found pyright’s missing config,
   but were never individually evaluated, only surfaced later
   because the person asked "did we miss anything" directly, not
   because the review process caught it on its own.
5. **Does every CHANGELOG.md entry claiming to close an issue
   actually have that issue closed on GitHub, checked directly, not
   assumed from the changelog text alone?**
   ← rule: `DEFINITION_OF_DONE.md`, Additional checks
   *Earned by:* v0.8.0’s own CHANGELOG.md entry said, "Closes #11,"
   but #11 was still open on GitHub when checked. Writing "Closes
   #N" in a changelog’s own prose does not close anything
   automatically, unlike a commit message or PR description, that is
   a separate, manual step, and it had been skipped.

6. **For a CLI/user-facing interface change, was the test coverage
   deliberately expanded beyond what a draft or static-only analysis
   proposed as enough, and actually run against the real code
   before trusting it?**
   ← rule: `DEFINITION_OF_DONE.md`, Correctness ("What would a
   deliberately adversarial reader try to break, given the actual
   code, not the intended behavior? Try that.")
   *Earned by:* #51’s argparse migration draft, produced by static
   reasoning alone (never executed against real code, by design),
   suggested two new tests as adequate. It asserted all 12 existing
   tests would pass unchanged — both true, but insufficient. Applying
   the change for real and running an expanded, more thorough test
   set (prompted by "this is direct UI and has to work flawlessly,"
   not by the draft’s own analysis) surfaced two real bugs the draft
   missed entirely: `argparse`’s default `allow_abbrev=True` silently
   accepted the typo `--onl` as a valid abbreviation of `--only`,
   defeating the typo-safety improvement the migration was meant to
   deliver. A separate, existing crash-handling test, never
   monkeypatching `sys.argv`, was unknowingly parsing pytest’s own
   real command-line flags. It passed "by coincidence" rather than
   actually exercising the crash path — invisible to any review that
   reasoned about the code without running it.

7. **Was a finding produced under a flag that disables the underlying
   check entirely (like `--disable=all`), not just narrows which
   messages display, re-verified against the real, full config
   before being trusted?**
   ← rule: `DEFINITION_OF_DONE.md`, Correctness
   *Earned by:* #47's original investigation used `--disable=all
   --enable=<5 messages>` to isolate a handful of pylint messages.
   `--disable=all` disables the underlying checks themselves, not
   just their display, so every local `# pylint: disable=` comment
   for an already-globally disabled check trivially showed as
   `useless-suppression`, an artifact of the test, not a genuine
   finding. 19 "stale suppressions" were reported this way,
   none of them were real. Caught only by running the actual, full config
   directly and finding just two genuine results, a real, significant
   difference from the original count.

8. **For every implementation change, was a deliberate test matrix
   run covering normal behavior, edge and boundary cases, meaningful
   combinations, and relevant negative or error paths?**
   ← rule: `DEFINITION_OF_DONE.md`, Correctness
   *Earned by:* #179's initial JSON tests covered selected values but
   omitted important combinations and negative paths. Expanding the
   tests exposed a real implementation bug. A passing happy-path test
   and a request to "add more tests" are not a substitute for this
   matrix.

9. **For a release-sensitive or packaging change, was the installed
   wheel and source distribution exercised through the real user-facing
   entry point, independently of the editable checkout?**
   ← rule: `DEFINITION_OF_DONE.md`, Release artifacts are tested as
   installed artifacts
   *Earned by:* the source-level suite passed while confidence in the
   release path still required separate wheel and source-distribution
   installation checks. Editable-source tests cannot expose an
   incomplete manifest, missing entry point, or artifact-only runtime
   discrepancy.

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
