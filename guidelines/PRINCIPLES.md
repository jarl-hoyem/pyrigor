# Principles

Enduring principles adopted for developing and maintaining Pyrigor.

These are project-level principles. They guide engineering decisions.
They are not, by themselves, Pyrigor rules for user code.

Every principle below is adopted and applies to project development. A
principle that is proposed rather than adopted, or scoped more
narrowly, says so in its own entry.

These are considerations, not rules, and they will sometimes pull
against each other. YAGNI and Unreasonable Hospitality collide on
almost every polish decision. Resolve a genuine conflict deliberately
and record the reasoning in `guidelines/DECISIONS.md`. No principle
overrides another by default.

## Chesterton's Fence

**Principle:** Understand why an existing mechanism exists before
removing or substantially changing it.

**Application to Pyrigor:** Before removing or substantially changing
existing behaviour, rules, architecture, documentation, or processes,
establish why they exist. Preserve the underlying purpose unless there
is a deliberate reason to change it.

## KISS

**Principle:** Prefer the simplest design that satisfies the actual
requirements. Treat unnecessary complexity as something that requires
justification.

**Application to Pyrigor:** Keep the architecture, the implementation,
CLI, rule model, configuration, documentation, and workflow as simple
as the real requirements allow. Simple does not mean simplistic:
complexity justified by correctness, security, performance,
compatibility, or maintainability is acceptable.

## Inversion

**Principle:** Instead of asking only how to achieve a desired outcome,
ask what would cause the outcome to fail, and design to prevent those
failure modes.

**Application to Pyrigor:** Use failure-oriented thinking when designing
rules, architecture, tests, workflows, and release processes. Before
accepting a design, explicitly ask how it could produce a false
positive, false negative, silent regression, unusable API, broken
release, or misleading result.

## YAGNI

**Principle:** Do not build functionality, abstraction, or flexibility
until a real requirement makes it necessary.

**Application to Pyrigor:** Build the rules, architecture, interfaces,
configuration, and tooling that Pyrigor needs now. Do not add
speculative generality merely because a future rule, language feature,
backend, integration, or user may eventually require it. Invest in
keeping the code easy to change instead of implementing hypothetical
future requirements.

## Sunk Cost Fallacy

**Principle:** Past, unrecoverable investment should not determine what
is best from today forward.

**Application to Pyrigor:** When reconsidering code, architecture,
dependencies, tooling, processes, or project direction, evaluate future
cost, risk, and value rather than defending an approach because effort
has already been invested. Existing assets should be retained when they
have genuine future value, not merely because they are already paid
for.

## Single Source of Truth

**Principle:** Each piece of authoritative information should have one
authoritative source. Derived representations should not become
competing authorities.

**Application to Pyrigor:** Keep guidelines, rule definitions,
configuration, specifications, and other authoritative project
information in one clearly identified source wherever practical.
Generated or duplicated representations must derive from that source
rather than silently becoming alternative authorities.

**Enforced by:** `pyrigor/rules.py` as the single rule declaration,
`scripts/generate_rule_table.py`, and `tests/test_rules_docs_sync.py`.

## Independent Verification

**Principle:** Do not accept a critical result solely because the
process that produced it says it is correct. Verify it through an
independent source of evidence.

**Application to Pyrigor:** For critical changes, seek verification that
is independent enough of the original production process. This can
include an independent agent or reviewer, a different analysis tool,
independently derived expected results, mutation testing, differential
testing, or human review against the specification. Scale the strength
of verification to the consequence of being wrong. A release or a
security-relevant change earns more independent evidence than a
documentation correction.

**Enforced by:** `guidelines/ISSUE_REVIEW.md` and the review checkbox
in the issue template.

## Specification Before Implementation

**Principle:** Define the required behaviour, relevant constraints, and
acceptance criteria before implementing a significant change.

**Application to Pyrigor:** Before implementing a significant rule,
architectural change, or behavioural change, establish the required
behaviour and acceptance criteria first. For rules, this includes the
violation, valid counterexamples, exceptions, diagnostic behaviour, and
expected results where relevant.

**Enforced by:** `guidelines/DEFINITION_OF_READY.md`.

## Never Let the Generator Be Its Own Oracle

**Principle:** A system or agent that produces an implementation must
not be the sole authority for deciding that the implementation is
correct.

**Application to Pyrigor:** Separate generation from authoritative
verification where practical. AI agents may generate code and tests,
but correctness should be established through a specification,
independently derived tests, existing reference behaviour, a different
tool or agent, human review, or other independent evidence. This
constrains who may judge correctness. Independent Verification
constrains what counts as evidence. A change can satisfy one and fail
the other.

## A Check That Cannot Fail Is Not a Check

**Principle:** A passing result is evidence only when the check could
have failed and when it is known to have run over the intended input.

**Application to Pyrigor:** Design every check so that "it passed" and
"it did not run" look different. Report what was covered, not only what
was found. This project has produced that failure repeatedly, including
an inspection that analysed one file and declared success (#229). Before
accepting a check, ask what its output would be if it did nothing at
all and make that case visible.

**Enforced by:** review, against `guidelines/DEFINITION_OF_DONE.md`.

## Tests Are the Executable Specification

**Principle:** Tests should express the required observable behaviour of
the software in an executable form.

**Application to Pyrigor:** For significant behaviour, tests should make
the intended contract concrete: what must be accepted, what must be
rejected, what diagnostics are expected, and what important edge cases
must hold. Tests should be readable enough to serve as an executable
description of the requirement.

**Additional requirement:** The test suite must also protect against
regression in test effectiveness. Changes must not reduce the mutation
score below the floor that `scripts/check_mutation_score.py` enforces.
That script holds the value. This document does not restate it. The
floor is a project-level quality gate, not a per-change target to be
met by weakening the mutation test suite.

**Enforced by:** `scripts/check_mutation_score.py` and the
`mutation-test` CI job.

## Measure, Do Not Guess

**Principle:** Base engineering decisions about performance, behaviour,
quality, and improvement on relevant evidence and measurements rather
than intuition alone.

**Application to Pyrigor:** Use evidence when making claims about
performance, false-positive and false-negative rates, test coverage, CI
duration, rule usefulness, release quality, and other measurable
properties of Pyrigor.

Knuth put the older form of this in 1974: "premature optimization is
the root of all evil." The line is usually quoted without the condition
attached to it, which is that the caution covers the small efficiencies
making up most of a program, not the small fraction where the cost
actually sits. Both halves apply here. The shared AST walk exists
because profiling against Home Assistant core, 18,187 files, found
`ast.walk` itself dominating, and that is the fraction where the work
was worth doing. See `guidelines/DECISIONS.md` and `PERFORMANCE.md`.

## No History Lessons

**Principle:** Code and ordinary documentation should describe the
current state and, where useful, why it is so. They should not narrate
how it evolved to get there.

**Application to Pyrigor:** Keep durable rationale in documentation when
it helps future maintainers understand a current design. Put
chronological development history in Git, issues, and pull requests,
rather than cluttering current code and documentation with the story of
how the current state was reached. Durable design rationale belongs in
`guidelines/DECISIONS.md`, which is a deliberate exception to this
principle rather than a violation of it.

## Unreasonable Hospitality

**Principle:** Make the experience for users and contributors wonderful,
not merely adequate.

**Application to Pyrigor:** Treat documentation, error messages, CLI
behaviour, onboarding, issue handling, release communication, and
contributor experience as products in their own right. Look for
opportunities to remove friction and provide useful guidance beyond the
minimum required for functionality.
