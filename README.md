# pyrigor

Disciplined Python patterns for catching bugs that type checkers and
standard linters miss — inspired by safety-critical coding guidelines from
other languages, adapted for a language and ecosystem they were not written
for.

## What this is

Python’s failure modes are often silent: implicit type coercion,
positional-argument swaps between same-typed parameters, mutable default
arguments, float equality checks, and tuple-unpacking that "type-checks"
while being semantically wrong are all real, tool-catchable classes of
bugs that slip past mypy, pylint, and ruff’s default rule sets.

`pyrigor` collects a set of guidelines — and, over time, tooling to enforce
them — aimed at closing those gaps.

## Status

Early stage. As of 2026-08, a set of documented guidelines. AST-based checks are
in progress. Plugin integration (pylint, possibly ruff) is a future goal,
not a current feature.

- [x] Guideline documentation
- [ ] Standalone AST-based checkers (pre-commit local hooks)
- [ ] pylint plugin
- [ ] ruff plugin (stretch goal — contingent on learning Rust)

## Guidelines

See [`guidelines/`](./guidelines) for the full list. Each guideline has a
rule ID, rationale, example, and — once implemented — a link to its
enforcing check.

Guidelines documented so far:

| ID     | Rule                                                                | Enforced by         |
|--------|---------------------------------------------------------------------|---------------------|
| PYR401 | Use `NamedTuple` for any function returning more than one value     | Not yet implemented |
| PYR201 | Use `NewType` for same-typed values at risk of being swapped        | Not yet implemented |
| PYR402 | Force keyword-only arguments for all function parameters (bare `*`) | Not yet implemented |

## Philosophy

Prefer explicit over implicit. Make illegal states unrepresentable. Do not
rely on convention or code review where a tool can enforce correctness
instead.

## Contributing

Not yet accepting contributions — still finding its shape. We will update this
section once there is a stable core to contribute to.

## License

MIT
