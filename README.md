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

Early stage. As of mid 2026, two rules are implemented and enforced
(PYR401, PYR402). Five more are documented but not yet enforced.

- [x] Guideline documentation
- [x] Standalone AST-based checkers (pre-commit local hooks) — PYR401,
  PYR402 implemented. PYR201, PYR202, PYR301, PYR403, PYR405 are documented
  but not yet enforced.
- [ ] pylint plugin
- [ ] ruff plugin (stretch goal — contingent on learning Rust)

## Usage

```bash
pip install pyrigor
pyrigor path/to/file.py [path/to/another.py ...]
```

PYR401 and PYR402 are enforced today. A violation exits non-zero and
prints `path:line:col: PYR40x message (symbolic-name)`.

To suppress a specific violation, add a same-line comment with a
reason:

```python
def f(weight, bias):  # pyrigor: PYR402 # matches a fixed external API
    ...
```

Codes may be given as the full code (`PYR402`), the bare number
(`402`), or the rule’s symbolic name (`keyword-only-arguments`).
Multiple codes: `# pyrigor: 402,403 # reason`. A suppression comment
without a reason is ignored, and a warning is printed.

## Guidelines

See [`guidelines/`](./guidelines) for the full list. Each guideline has a
rule ID, rationale, example, and — once implemented — a link to its
enforcing check.

Guidelines documented so far:

| ID     | Rule                                                                  | Enforced by                     |
|--------|-----------------------------------------------------------------------|---------------------------------|
| PYR201 | Use `NewType` for same-typed values at risk of being swapped          | Not yet implemented             |
| PYR202 | Use `Enum` instead of magic strings, ints, or bools for closed states | Not yet implemented             |
| PYR203 | Use `Final` named constants instead of magic numbers                  | Not yet implemented             |
| PYR204 | Never compare floats with `==`; use tolerance-based comparison        | Not yet implemented             |
| PYR301 | Use `NamedTuple` instead of a bare fixed-length `tuple` type          | Not yet implemented             |
| PYR302 | Use `frozen=True` for dataclasses holding structured state            | Not yet implemented             |
| PYR401 | Use `NamedTuple` for any function returning more than one value       | `pyrigor` CLI (pre-commit hook) |
| PYR402 | Force keyword-only arguments for 2+ function parameters (bare `*`)    | `pyrigor` CLI (pre-commit hook) |
| PYR403 | Force keyword-only arguments for single-parameter functions           | Not yet implemented             |
| PYR404 | Use immutable default argument values, never mutable ones             | Not yet implemented             |
| PYR405 | Use `NamedTuple` for multi-value parameter types, not bare `tuple`    | Not yet implemented             |
| PYR501 | End a `match` over a closed set with `case _: assert_never(...)`      | Not yet implemented             |
| PYR502 | State implicit input assumptions as explicit `assert` preconditions   | Not yet implemented             |

## Philosophy

Prefer explicit over implicit. Make illegal states unrepresentable. Do not
rely on convention or code review where a tool can enforce correctness
instead.

The tool pyrigor is prescriptive by design: each guideline does not just flag a
risky pattern, it commits to one specific, verified fix. This is a
deliberate choice, not an oversight — a codebase where every developer
independently improvises their own fix for the same problem is exactly
the inconsistency pyrigor exists to close.

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the setup and workflow.

## License

MIT
