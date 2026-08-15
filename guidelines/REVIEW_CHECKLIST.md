# Review checklist

A Fagan-Inspection-style checklist, in the sense of Gilb and Graham's
*Software Inspection*: checklist questions derive their authority
from a rule, are earned one at a time by a real defect that slipped
through, and are pruned if they stop finding anything. Not
brainstormed, not copied from elsewhere.

Format: each question is phrased so a **no** answer means an issue
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
   any process at the time.

## Adding a question

A question is only added here after a real defect slipped through
that this checklist, if it had existed with that question already on
it, would have caught. Log the defect and which question would have
caught it, in the entry itself, the same way each entry above does.

Do not add a question because it seems like good practice in the
abstract. That produces exactly the "obvious or irrelevant" checklist
*Software Inspection* warns against, one that looks thorough but
does not actually find anything, because it was never tied to a real
failure.

## Removing a question

If a question has not caught anything over a reasonable period,
across enough real feature work to have had a chance to, remove it.
An unused question makes the checklist longer without making it more
effective, and erodes trust in the ones that do work.
