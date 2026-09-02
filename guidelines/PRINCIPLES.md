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
