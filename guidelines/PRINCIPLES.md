# Principles

Enduring principles adopted for developing and maintaining Pyrigor.

These are project-level principles. They guide engineering decisions; they are not, by themselves, Pyrigor rules for user code.

## Chesterton's Fence

**Principle:** Understand why an existing mechanism exists before removing or substantially changing it.

**Application to Pyrigor:** Before removing or substantially changing existing behaviour, rules, architecture, documentation, or processes, establish why they exist. Preserve the underlying purpose unless there is a deliberate reason to change it.

**Scope:** Project development

**Status:** Adopted

### Analysis

**Value:** High. Pyrigor is an evolving codebase and is increasingly being modified with AI assistance. Existing checks, tests, interfaces, compatibility behaviour, and documentation may encode constraints whose purpose is not obvious from the local code. Understanding that purpose before changing them reduces the risk of removing a useful safeguard or reintroducing a previously solved problem.

**Evidence:** The principle originates with G. K. Chesterton's 1929 *The Thing*. The underlying idea is that an unexplained existing constraint should not be removed merely because its purpose is not immediately visible. It is also widely applied to legacy software and refactoring.

**Important qualification:** Chesterton's Fence is not a command to preserve existing things indefinitely. Understanding the original purpose is a prerequisite to making an informed change, not an argument that the original design remains correct. Once the purpose and current requirements are understood, the fence may be removed or replaced.

**Operational test:** Before removing or substantially changing an existing mechanism, answer:

1. What problem was it intended to solve?
2. Is that problem still relevant?
3. What other behaviour depends on it?
4. What evidence shows that removing or changing it is safe?
5. If the original reason no longer applies, what replaces the protection it provided, if anything?

**AI-assisted development:** This principle is especially important when an AI-generated change describes existing code as redundant, unnecessary, or overly complex. The claim is a hypothesis to verify, not evidence that the mechanism can safely be removed.

**Boundary:** This principle applies to changes to existing Pyrigor behaviour and structure. It does not require researching the historical origin of every line of code before ordinary maintenance or improvement.

## Inversion

**Principle:** Instead of asking only how to achieve a desired outcome, ask what would cause the outcome to fail, and design to prevent those failure modes.

**Application to Pyrigor:** Use failure-oriented thinking when designing rules, architecture, tests, workflows, and release processes. Before accepting a design, explicitly ask how it could produce a false positive, false negative, silent regression, unusable API, broken release, or misleading result.

**Scope:** Project development

**Status:** Adopted

### Analysis

**Value:** High. Pyrigor is a quality tool: its most damaging failures are often not crashes but confidently producing the wrong result, missing a defect, or making correct code appear incorrect. Inversion directs attention toward exactly these failure modes.

**Evidence:** Inversion is a long-established reasoning technique and is strongly associated with Charlie Munger's use of mental models. It is also closely related to established engineering practices such as failure-mode analysis, negative testing, threat modeling, and root-cause analysis. Those practices provide stronger engineering grounding than the slogan alone.

**Why it fits Pyrigor:** A normal design question is "How do we detect this pattern?" The inverted questions are at least as important: "How could this rule flag correct code?", "How could it miss an actual violation?", and "How could its implementation become unsound as Python evolves?" The same approach applies to the project itself: "How could this architecture make adding the next 100 rules expensive?" or "How could an AI-generated change silently weaken verification?"

**Operational test:** For a significant project decision, identify the important ways the decision could fail before finalizing it. Where practical, turn the important failure modes into tests, invariants, quality gates, or explicit design constraints.

**Important qualification:** Inversion is a reasoning technique, not a requirement to enumerate every imaginable failure. Apply it proportionately to the risk and significance of the decision.

**Boundary:** This principle governs engineering reasoning and verification. It does not mean that every Pyrigor rule should literally be expressed as a negative rule or that every implementation needs exhaustive failure analysis.

## YAGNI

**Principle:** Do not build functionality, abstraction, or flexibility until a real requirement makes it necessary.

**Application to Pyrigor:** Build the rules, architecture, interfaces, configuration, and tooling that Pyrigor needs now. Do not add speculative generality merely because a future rule, language feature, backend, integration, or user may eventually require it. Invest in keeping the code easy to change instead of implementing hypothetical future requirements.

**Scope:** Project development

**Status:** Adopted

### Analysis

**Value:** High. Pyrigor has a large potential rule space and an evolving Rust/Python architecture. Without YAGNI, it would be easy to build generalized infrastructure for rules or future integrations before the actual requirements are known. That creates complexity and maintenance cost while potentially encoding assumptions that later prove wrong.

**Evidence:** YAGNI originated in the Extreme Programming (XP) community and was popularized as a named practice in software engineering. Martin Fowler describes it as avoiding code for capabilities that are only presumed to be needed later, including speculative abstractions.

**Important qualification:** YAGNI does not mean "never prepare for change." It distinguishes speculative functionality from work that makes software easier to change, such as refactoring and automated testing. A change that improves malleability without implementing a hypothetical feature is compatible with YAGNI.

**Operational test:** Before adding functionality or abstraction primarily for a future need, ask: "What current requirement needs this?" If there is no concrete current requirement, defer it unless the extra capability has an independent present-day value.

**AI-assisted development:** Treat AI proposals for "future-proofing," generalized frameworks, extension points, configuration options, or abstractions as proposals requiring justification. The existence of a plausible future use is not sufficient justification.

**Relationship to other principles:** YAGNI reinforces KISS by limiting unnecessary complexity. Sunk Cost Fallacy prevents past investment from becoming a reason to continue speculative work. Chesterton's Fence prevents YAGNI from becoming an excuse to remove existing mechanisms without understanding their purpose.

**Boundary:** YAGNI applies to speculative capability and complexity. It does not prohibit sound foundations, refactoring, testing, security measures, compatibility requirements, or other work that provides current value or makes the system safely changeable.

## Independent Verification

**Principle:** Do not accept a critical result solely because the process that produced it says it is correct; verify it through an independent source of evidence.

**Application to Pyrigor:** For critical changes, seek verification that is sufficiently independent of the original production process. This can include an independent agent or reviewer, a different analysis tool, independently derived expected results, mutation testing, differential testing, or human review against the specification.

**Scope:** Project development

**Status:** Adopted

### Analysis

**Value:** High. AI-assisted development creates a particular risk: an agent can generate code, generate tests for that code, run those tests, and then conclude that the implementation is correct. That can create a closed feedback loop in which the generator effectively becomes its own oracle.

**Meaning:** Independence concerns how the verification was derived and which assumptions it shares with the implementation. Merely running the same test suite twice is not independent verification.

**Why it fits Pyrigor:** Pyrigor is a quality tool, so incorrect results are especially dangerous. An implementation that passes only checks derived from the same assumptions that produced it can still be wrong. Independent verification provides a second line of reasoning rather than another execution of the same reasoning.

**Operational test:** For a critical change, identify at least one verification path whose assumptions, implementation, or evaluator are meaningfully independent of the original implementation. Prefer multiple independent forms of evidence for high-risk changes.

**AI-assisted development:** Claude Code, Codex, or another generator may implement a change and propose tests, but the generated result should not be treated as self-authenticating. Independent review, independently derived tests, or different tools should be used where the risk justifies them.

**Important qualification:** Independence is relative, not binary. Two tools may share the same flawed specification; two agents may reproduce the same mistaken assumption. The goal is to reduce correlated failure, not to demand impossible absolute independence.

**Relationship to other principles:** This directly reinforces **Never Let the Generator Be Its Own Oracle**, **Tests Are the Executable Specification**, **Inversion**, and **Trust but Verify**.

**Boundary:** Apply the principle proportionately. Not every trivial edit requires a second human review or an elaborate independent verification process; criticality should determine the strength of the independent check.

## Specification Before Implementation

**Principle:** Define the required behaviour, relevant constraints, and acceptance criteria before implementing a significant change.

**Application to Pyrigor:** Before implementing a significant rule, architectural change, or behavioural change, establish the required behaviour and acceptance criteria first. For rules, this includes the violation, valid counterexamples, exceptions, diagnostic behaviour, and expected results where relevant.

**Scope:** Project development

**Status:** Adopted

### Analysis

**Value:** High. Pyrigor is developed with AI assistance, so an underspecified task allows an agent to fill gaps with assumptions and produce a technically plausible implementation that solves the wrong problem. This is particularly risky for static-analysis rules, where intended semantics and exceptions matter as much as implementation.

**Evidence:** The principle is strongly supported by requirements engineering, formal methods, contract-based development, and TDD practices. It is better understood as a family of established engineering practices than as a single universally named law.

**Operational test:** Before implementation, define what must be true and how the result will be accepted. The specification should be precise enough that implementation and verification can be evaluated against it independently.

**Important qualification:** Specification does not mean exhaustive up-front design. Keep it proportional to the decision and precise about what matters. If implementation reveals a new requirement, update the specification rather than silently making the implementation the specification.

**AI-assisted development:** Claude Code, Codex, or another agent should receive a clear target and acceptance criteria rather than being asked to infer the desired design from a vague task. The specification remains authoritative over the generated implementation.

**Relationship to other principles:** Reinforces YAGNI by defining actual requirements, Independent Verification by providing an independent basis for judging the implementation, and Tests Are the Executable Specification by providing the source from which tests can be derived.

**Boundary:** Applies to significant changes; trivial edits need not require a formal specification.