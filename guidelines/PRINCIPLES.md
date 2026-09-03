# Principles

Enduring principles adopted for developing and maintaining Pyrigor.

These are project-level principles. They guide engineering decisions; they are not, by themselves, Pyrigor rules for user code.

## Chesterton's Fence

**Principle:** Understand why an existing mechanism exists before removing or substantially changing it.

**Application to Pyrigor:** Before removing or substantially changing existing behaviour, rules, architecture, documentation, or processes, establish why they exist. Preserve the underlying purpose unless there is a deliberate reason to change it.

**Scope:** Project development

**Status:** Adopted

## KISS

**Principle:** Prefer the simplest design that satisfies the actual requirements; treat unnecessary complexity as something that requires justification.

**Application to Pyrigor:** Keep the architecture, Rust/Python implementation, CLI, rule model, configuration, documentation, and workflow as simple as the real requirements allow. Simple does not mean simplistic: complexity justified by correctness, security, performance, compatibility, or maintainability is acceptable.

**Scope:** Project development

**Status:** Adopted

## Inversion

**Principle:** Instead of asking only how to achieve a desired outcome, ask what would cause the outcome to fail, and design to prevent those failure modes.

**Application to Pyrigor:** Use failure-oriented thinking when designing rules, architecture, tests, workflows, and release processes. Before accepting a design, explicitly ask how it could produce a false positive, false negative, silent regression, unusable API, broken release, or misleading result.

**Scope:** Project development

**Status:** Adopted

## YAGNI

**Principle:** Do not build functionality, abstraction, or flexibility until a real requirement makes it necessary.

**Application to Pyrigor:** Build the rules, architecture, interfaces, configuration, and tooling that Pyrigor needs now. Do not add speculative generality merely because a future rule, language feature, backend, integration, or user may eventually require it. Invest in keeping the code easy to change instead of implementing hypothetical future requirements.

**Scope:** Project development

**Status:** Adopted

## Sunk Cost Fallacy

**Principle:** Past, unrecoverable investment should not determine what is best from today forward.

**Application to Pyrigor:** When reconsidering code, architecture, dependencies, tooling, processes, or project direction, evaluate future cost, risk, and value rather than defending an approach because effort has already been invested. Existing assets should be retained when they have genuine future value, not merely because they are already paid for.

**Scope:** Project development

**Status:** Adopted

## Single Source of Truth

**Principle:** Each piece of authoritative information should have one authoritative source; derived representations should not become competing authorities.

**Application to Pyrigor:** Keep guidelines, rule definitions, configuration, specifications, and other authoritative project information in one clearly identified source wherever practical. Generated or duplicated representations must derive from that source rather than silently becoming alternative authorities.

**Scope:** Project development

**Status:** Adopted

## Independent Verification

**Principle:** Do not accept a critical result solely because the process that produced it says it is correct; verify it through an independent source of evidence.

**Application to Pyrigor:** For critical changes, seek verification that is sufficiently independent of the original production process. This can include an independent agent or reviewer, a different analysis tool, independently derived expected results, mutation testing, differential testing, or human review against the specification.

**Scope:** Project development

**Status:** Adopted

## Specification Before Implementation

**Principle:** Define the required behaviour, relevant constraints, and acceptance criteria before implementing a significant change.

**Application to Pyrigor:** Before implementing a significant rule, architectural change, or behavioural change, establish the required behaviour and acceptance criteria first. For rules, this includes the violation, valid counterexamples, exceptions, diagnostic behaviour, and expected results where relevant.

**Scope:** Project development

**Status:** Adopted

## Never Let the Generator Be Its Own Oracle

**Principle:** A system or agent that produces an implementation must not be the sole authority for deciding that the implementation is correct.

**Application to Pyrigor:** Separate generation from authoritative verification where practical. AI agents may generate code and tests, but correctness should be established through a specification, independently derived tests, existing reference behaviour, a different tool or agent, human review, or other independent evidence.

**Scope:** Project development

**Status:** Adopted

## Tests Are the Executable Specification

**Principle:** Tests should express the required observable behaviour of the software in an executable form.

**Application to Pyrigor:** For significant behaviour, tests should make the intended contract concrete: what must be accepted, what must be rejected, what diagnostics are expected, and what important edge cases must hold. Tests should be readable enough to serve as an executable description of the requirement.

**Additional requirement:** The test suite must also protect against regression in test effectiveness. Changes must not reduce the established Mutmut mutation-score floor. The floor is a project-level quality gate, not a per-change target to be optimized by weakening the mutation test suite.

**Scope:** Project development

**Status:** Adopted

## Measure, Don't Guess

**Principle:** Base engineering decisions about performance, behaviour, quality, and improvement on relevant evidence and measurements rather than intuition alone.

**Application to Pyrigor:** Use evidence when making claims about performance, false-positive and false-negative rates, test coverage, CI duration, rule usefulness, release quality, and other measurable properties of Pyrigor.

**Scope:** Project development

**Status:** Adopted

## No History Lessons

**Principle:** Code and ordinary documentation should describe the current state and, where useful, why it is so—not narrate how it evolved to get there.

**Application to Pyrigor:** Keep durable rationale in documentation when it helps future maintainers understand a current design. Put chronological development history in Git, issues, pull requests, or other historical records rather than cluttering current code and documentation with the story of how the current state was reached.

**Scope:** Project development

**Status:** Adopted

## Unreasonable Hospitality

**Principle:** Make the experience for users and contributors exceptionally good, not merely adequate.

**Application to Pyrigor:** Treat documentation, error messages, CLI behaviour, onboarding, issue handling, release communication, and contributor experience as products in their own right. Look for opportunities to remove friction and provide useful guidance beyond the minimum required for functionality.

**Scope:** Project development

**Status:** Adopted

## Trust but Verify

**Principle:** Trust useful work and claims provisionally, but verify important ones before relying on them.

**Application to Pyrigor:** Treat generated code, test results, benchmarks, documentation claims, and external assertions as evidence rather than unquestionable truth. The strength of verification should be proportional to the consequence of being wrong.

**Scope:** Project development

**Status:** Adopted
