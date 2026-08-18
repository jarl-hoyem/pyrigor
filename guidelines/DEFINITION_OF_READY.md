# Definition of ready

A companion to `DEFINITION_OF_DONE.md`. The `DEFINITION_OF_DONE.md`
covers when a piece of work is finished. This covers when a piece of
work is ready to start.

An issue is ready to be worked on when:

- It is assigned to a developer.
- It has both a `value:` and an `effort:` label. Both axes matter,
  not effort alone. Prioritization depends on the relationship
  between them.
- It has a type label (`bug`, `enhancement`, `documentation`,
  `technical debt / refactoring`, `testing`, `rule`, or `tooling`).
- The description contains real criteria for when the issue is done,
  not just a problem statement. For a new rule, this means pointing
  at `ADDING_A_RULE.md`'s own checklist. For anything else, a
  concrete, checkable outcome.
- The proposed scope is not narrowed specifically to avoid touching
  existing tests or code. If it is, that is the sunk-cost fallacy,
  not a real scoping decision.
- Whoever is assigned agrees they understand what to do and has no
  open questions.

## Planning issues

If an issue is unclear, larger than the largest effort size (`L`,
there is no bigger size, see `CONTRIBUTING.md`'s sizing section),
involves a real architectural decision, or blocks multiple other
issues, it is not ready as-is. Create a planning issue instead: a
smaller, sized issue whose entire scope is analyzing the problem and
splitting it into real, linked, individually ready issues. The
planning issue is done once those real issues exist and are
themselves ready.
