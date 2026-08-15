# Definition of done

A short, standing check to apply before declaring any feature, flag,
or fix complete, in every session, regardless of whether this file
was read before. Written for whichever instance of Claude is working
on this project, since nothing carries forward between separate
conversations except what is written here.

## The rule

Before saying something is done, list every property it was
explicitly claimed to have during this conversation, then confirm a
test exists for each one, individually. Do not infer "tests pass" as
"every claimed property is tested." A passing test suite only proves
correctness for what was actually tested.

This applies with extra force when a feature is scoped as "behaves
like an existing feature." In that case, the existing feature’s own
test file is the checklist. Read it. Confirm an equivalent test
exists for each tested behavior in the new feature too,
before calling the new feature done.

"Tested" means more than the happy path, and the one case explicitly
discussed. Before calling something done, deliberately construct the
test cases that would give real confidence few errors remain, not
just the cases that occurred while building it. For each new piece
of logic, ask:

- What are the equivalence classes of input, and is at least one
  case tested from each, not just the one that motivated the change?
- What are the boundary values (zero, one, the maximum, the minimum,
  empty, none), and is each boundary tested on both sides of it?
- What is the error path, and is it tested deliberately, not just
  assumed to work because the happy path does?
- What would a deliberately adversarial reader try to break, given
  the actual code, not the intended behavior? Try that.

This is the same discipline `ADDING_A_RULE.md` already applies to
checkers specifically (self/cls, async, positional-only, single
element). Apply it to every piece of new logic, not only checkers.

"Done" also includes documentation. Before saying something is
finished, check whether it changed anything a user-facing doc
(README.md, CHANGELOG.md) or a design doc (guidelines/) claims about
the project. Update those files as part of finishing the work,
not as a separate step performed only when asked.

## Why this exists

`--only` was scoped, explicitly, as "the same lenient forms as
suppression comments." It shipped, declared done, with tests for
code-form and symbolic-name-form only. Whitespace tolerance,
something suppression comments already have a dedicated test for,
was never checked. The user asked a pointed follow-up question and
caught it. This should have been caught before the feature was
called done, by cross-referencing suppression’s own test list, which
already existed and already covered exactly this case.

## What this is not

Not a call for a formal requirements document before every feature.
Not a call for process weight the maintainer has repeatedly and
deliberately rejected elsewhere in this project (see CONTRIBUTING.md
and the Sprint-cadence removal in its own history). This is a check
performed silently, before saying "done," not a document to produce
for review.

## Precedent

`ADDING_A_RULE.md` already solves this exact problem for one
category of work (checkers): a written checklist of required test
cases (self/cls, async, positional-only, ...), read at the
start of building any rule, regardless of whether the same mistake
was already made once before. This file is the same pattern, applied
to features and CLI behavior, not just checkers, because
the same category of gaps has now shown up twice in that domain
(`--version`'s coverage, `--only`'s leniency).

`guidelines/REVIEW_CHECKLIST.md` extends this further, in the style
of Gilb and Graham's *Software Inspection*: each checklist question
is earned by a real defect that slipped through, tagged back to the
rule it elaborates, not brainstormed in the abstract. Run it
alongside this file before declaring anything done.

## Additional checks

Standard software Definition of Done practice, filtered for a solo
OSS project (not verified against a current source, general
knowledge only):

- **No known regressions.** The full test suite passes, not just the
  new test for this change. Already standard practice here
  (`pre-commit run --all-files`), stated explicitly, so it is not
  skipped under time pressure.
- **Backward compatibility.** If this change alters any documented
  public behavior (a return type, a CLI flag’s shape, a rule’s
  scope), the version bump and `CHANGELOG.md` entry reflect that,
- not as a smaller change than it actually is.
- **`BACKLOG.md` traceability.** If this work closes an existing
  backlog entry, remove or mark it done. Do not leave it sitting as
  if still open.
- **Non-functional properties, when relevant.** If a change plausibly
  affects performance, `PERFORMANCE.md` gets a note. Not required for
  every change, only ones where it is a real question.
- **Gaps found later.** If a gap is found after work was already
  called done, in this session or a future one, add it to
  `BACKLOG.md` immediately. Do not let it go undocumented while
  moving on to something else.
-
