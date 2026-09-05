---
name: New issue (Definition of Ready)
about: Create an issue that meets this project's own readiness bar
---

## Problem or idea

<!-- What is the real problem, not just a symptom or a vague idea. -->

## In scope

<!-- List the work included in this issue. -->

## Out of scope

<!-- List related work deliberately excluded from this issue. -->

## Done when

<!-- Real, checkable done-criteria, not just a restated problem statement.
For a new rule, point at the 'ADDING_A_RULE.md' checklist instead of writing this from scratch.
Include the test matrix: Normal
behavior, edge/boundary cases, meaningful combinations, and relevant
negative/error paths. -->

## Readiness checklist

Structurally verifiable, not self-certified, apply these as real GitHub labels, not text below:

- [ ] A `value:` label is applied
- [ ] An `effort:` label is applied
- [ ] Assigned to a Milestone when a relevant one exists

<!-- Also apply a type label: bug, enhancement, documentation,
technical debt / refactoring, testing, rule in pyrigor, or tooling. -->

Self-certified, an honest check, not independently verifiable:

- [ ] The "Done when" section above states real, checkable criteria, not just a restated problem
- [ ] Considered whether this should be split smaller before filing it as one issue
- [ ] Checked the full label list in GitHub's label picker, not just the ones already mentioned above, for anything else
      that applies
- [ ] The issue has been independently reviewed using `guidelines/ISSUE_REVIEW.md`, and any material disagreement has
      been resolved

## Too big or unclear

If this is larger than the largest real effort size (`L`), involves a genuine architectural decision, or blocks several
other issues, stop. File a planning issue instead (see `guidelines/DEFINITION_OF_READY.md`'s "Planning issues" section),
not this template.
