# Definition of done

A short, standing check to apply before declaring any feature, flag,
or fix complete, in every session, regardless of whether this file
was read before. Written for whichever instance of Claude is working
on this project, since nothing carries forward between separate
conversations except what is written here.

## The rule

Before saying something is done, list every property the change is
claimed to have in its issue, acceptance criteria, documentation, or
implementation, then confirm a test exists for each one, individually.
Do not infer "tests pass" as
"every claimed property is tested." A passing test suite only proves
correctness for what was actually tested.

For every implementation change, deliberately build and run a test
matrix before declaring it done. The matrix must cover normal
behaviour, edge and boundary cases, meaningful combinations of options
or inputs, and relevant negative or error paths. If a category does
not apply, record that judgment rather than silently omitting it.
This is mandatory even when the initial request only says to
"add a test" or static analysis suggests that existing tests are
enough.

For every rule, also record whether name shadowing can affect its
result: none, partial, or full. Name-resolving rules must test every
applicable shadowing class. Syntax-only rules must explain why the
dimension does not apply. The shared matrix includes module and local
rebinding, nested functions, `global`, `nonlocal`, class bodies,
comprehensions, imports and aliases, arguments, exception aliases,
match bindings, sequential redefinitions, lambdas, and classes.

This applies with extra force when a feature is scoped as "behaves
like an existing feature." In that case, the existing feature’s own
test file is the checklist. Read it. Confirm an equivalent test
exists for each tested behaviour in the new feature too,
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
  the actual code, not the intended behaviour? Try that.

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
performed silently, before saying "done", not a document to produce
for review.

## Precedent

`ADDING_A_RULE.md` already solves this exact problem for one
category of work (checkers): a written checklist of required test
cases (self/cls, async, positional-only, ...), read at the
start of building any rule, regardless of whether the same mistake
was already made once before. This file is the same pattern, applied
to features and CLI behaviour, not just checkers, because
the same category of gaps has now shown up twice in that domain
(`--version`'s coverage, `--only`'s leniency).

`guidelines/REVIEW_CHECKLIST.md` extends this further, in the style
of Gilb and Graham’s *Software Inspection*: each checklist question
is earned by a real defect that slipped through, tagged back to the
rule it elaborates, not brainstormed in the abstract. Run it
alongside this file before declaring anything done.

The file `guidelines/DEFINITION_OF_READY.md` covers the other half
of the same boundary: not when work is finished, but when it is
ready to start (assigned, sized, real done criteria already in the
description, no open questions). Read it before picking up an
issue, the same way this file is read before closing one.

## Additional checks

Standard software Definition of Done practice, filtered for a solo
OSS project (not verified against a current source, general
knowledge only):

- **No known regressions.** The full test suite passes, not just the
  new test for this change. Already standard practice here
  (`just check`), stated explicitly, so it is not
  skipped under time pressure.
- **Release artefacts are tested as installed artefacts.** Before a
  release, build both the wheel and source distribution, install each
  in an isolated environment, and exercise the real CLI. Verify the
  entry point, clean output, diagnostics, JSON output, suppression,
  and operational errors. Source-checkout tests cannot prove that the
  package manifest, entry point, or artefact contents are correct.
- **Bug fixes get a reproducing test first.** Write the test that
  captures the reported bug before writing the fix, not after —
  confirms the fix actually addresses what was reported, not just a
  symptom near it, and locks in the regression.
- **Backward compatibility.** If this change alters any documented
  public behaviour (a return type, a CLI flag’s shape, a rule’s
  scope), the version bump and `CHANGELOG.md` entry reflect that,
  not as a smaller change than it actually is.
- **Issue traceability.** If this work closes an existing GitHub
  Issue, close it (see the close-at-changelog-entry-time rule
  below). Do not leave it sitting open as if the work were still
  pending.
- **Read every comment before closing.** Before closing a GitHub
  Issue as part of this work, read its full comment thread, not just
  the original description. A scope change, a raised question, or a
  still-open concern discussed there is easy to miss if only the
  description gets checked. Nothing should be left open or
  unanswered when the issue closes.
- **No sunk-cost bias in a design choice.** If an option is picked
  specifically because it avoids touching existing tests or code,
  rather than because it is the genuinely correct design, that is
  the sunk-cost fallacy, not a real trade-off. Prefer the right
  design and update whatever needs updating.
- **Non-functional properties, when relevant.** If a change plausibly
  affects performance, `PERFORMANCE.md` gets a note. Not required for
  every change, only ones where it is a real question.
- **Gaps found later.** If a gap is found after work was already
  called done, in this session or a future one, create a GitHub
  Issue for it immediately. Do not let it go undocumented while
  moving on to something else.
- Close the corresponding GitHub Issue at the same time a CHANGELOG.md
  entry referencing it is added under [Unreleased], not later, at
  release time. The changelog entry is the trigger. Waiting until
  release risks the close being forgotten entirely once [Unreleased]
  becomes a real, dated version heading, as happened with #11.
- Guideline docs, rule descriptions, and issue text describe the current,
  correct state, not the history of how they got that way. No
  "earlier version allowed...", no "this was fixed tonight", no
  narration of this project’s own past states or evolution. This is not
  a ban on citing real, external sources. Citing McConnell,
  OSSF, a style guide, or another real project’s own config is a
  legitimate citation anywhere in the project, never a history lesson.
- DECISIONS.md and REVIEW_CHECKLIST.md’s own "Earned by" sections are
  explicit exceptions to the no-project-history part specifically,
  their whole purpose is documenting past decisions and incidents.

## Releasing a version

1. **Update `CHANGELOG.md` first.** Move `[Unreleased]`'s content
   into a new `[X.Y.Z]` heading with the real date, add a fresh,
   empty `[Unreleased]` above it.
2. **Bump `pyproject.toml`'s version**, then run `uv lock`.
3. **Commit `pyproject.toml`, `uv.lock`, and `CHANGELOG.md` together,
   in one commit.** Not two. The changelog entry and the version bump
   describe the same release, they should land together, not have
   the changelog trail behind as an afterthought.
4. **Run the Key Performance Indicators (KPI) scans**
   (`guidelines/PROJECT_KPIS.md`) and record the new rows, in their own commit.
5. **Run pyscn's clone detection** (`uvx pyscn@latest analyze .
   --select clones`), review real findings against the known,
   deliberate architectural patterns (checker `find_violations`
   wrappers, `_shared.py`'s helper functions), file an issue for
   anything genuinely new.
6. **Run the PyCharm inspection** (`just inspect`), and check that the
   release's own changes drew no new findings outside the three known
   settings categories tracked in #236. Delete
   `.pycharm-inspection-results/` and `.pycharm-inspection.log`
   afterwards. This is the only scheduled moment the inspection runs,
   since it is too slow for pre-commit and its backlog is too large to
   gate on. See `DECISIONS.md`.
7. Push, then create the GitHub release/tag (`vX.Y.Z`, matching tag
   and title) with real release notes.

Dev-tooling-only changes (a new pre-commit hook, a CI workflow fix,
internal refactors with no user-visible behaviour change) do not need
a `CHANGELOG.md` entry. Only user-facing changes do.
