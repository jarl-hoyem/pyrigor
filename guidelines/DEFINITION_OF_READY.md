# Definition of ready

A companion to `DEFINITION_OF_DONE.md`. The `DEFINITION_OF_DONE.md`
covers when a piece of work is finished. This covers when a piece of
work is ready to start.

An issue is ready to be worked on when:

- It has both a `value:` and an `effort:` label. Both axes matter,
  not effort alone. Prioritization depends on the relationship
  between them.
- It has a type label (`bug`, `enhancement`, `documentation`,
  `technical debt / refactoring`, `testing`, `rule in pyrigor`, or `tooling`).
- The description contains real criteria for when the issue is done,
  not just a problem statement. For a new rule, this means pointing
  at `ADDING_A_RULE.md`'s own checklist. For anything else, a
  concrete, checkable outcome.
- Its scope has been checked for whether it can be split smaller
  before any work starts. Splitting after starting means real
  complexity was discovered the hard way, mid-flight. This is the
  same discipline behind Steve McConnell’s "miniature milestones"
  practice (*Rapid Development*): decompose before starting, not
  after.
- Every label from `CONTRIBUTING.md`'s full list has been checked
  against the issue, not just the required type/value/effort
  minimum. Multiple labels commonly apply together.
- Assigned to a Milestone when a relevant one exists
- Its full comment thread has been read, not just the description —
  scope may have changed or been clarified there after the filing.
- It has been independently reviewed by a second LLM before work
  commences. The review checks the specification, acceptance criteria,
  applicable principles and decisions, and potential unintended
  consequences. Any material disagreement has been resolved.

An issue meeting all the above gets the `ready` label. This does
not require an assignee. Assignment happens when someone
picks up a ready issue to actually start it, a separate, later act,
not a precondition for being ready.

## Every change starts with an issue

No branch or commit begins without a corresponding GitHub Issue
already existing. This applies even to small, solo work. An
issue-first, however brief, keeps a real record of what was done and
why, consistent with `CLAUDE.md`'s "Backlog and issue tracking"
section: all work goes through GitHub Issues.

## Planning issues

If an issue is unclear, larger than the largest effort size (`L`,
there is no bigger size, see `CONTRIBUTING.md`'s sizing section),
involves a real architectural decision, or blocks multiple other
issues, it is not ready as-is. Create a planning issue instead: a
smaller, sized issue whose entire scope is analyzing the problem and
splitting it into real, linked, individually ready issues. The
planning issue is done once those real issues exist and are
themselves ready.
