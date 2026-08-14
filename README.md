# pyrigor

[![PyPI version](https://img.shields.io/pypi/v/pyrigor.svg)](https://pypi.org/project/pyrigor/)
[![CI](https://github.com/jarl-hoyem/pyrigor/actions/workflows/ci.yaml/badge.svg)](https://github.com/jarl-hoyem/pyrigor/actions/workflows/ci.yaml)
[![Publish](https://github.com/jarl-hoyem/pyrigor/actions/workflows/publish.yaml/badge.svg)](https://github.com/jarl-hoyem/pyrigor/actions/workflows/publish.yaml)
[![Python 3.11-3.14](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://docs.astral.sh/ruff/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://pre-commit.com/)
[![Type hints: Pyright](https://img.shields.io/badge/type%20hints-Pyright-brightgreen.svg)](https://github.com/microsoft/pyright)
[![Type hints: mypy](https://img.shields.io/badge/type%20hints-mypy-brightgreen.svg)](http://mypy-lang.org/)
[![Type hints: ty](https://img.shields.io/badge/type%20hints-ty-brightgreen.svg)](https://github.com/astral-sh/ty)
[![Pylint](https://img.shields.io/badge/pylint-checked-brightgreen)](https://pylint.pycqa.org/)
[![pydocstyle](https://img.shields.io/badge/docstrings-pydocstyle-brightgreen)](http://www.pydocstyle.org/)
[![Complexity: xenon](https://img.shields.io/badge/complexity-xenon-brightgreen)](https://xenon.readthedocs.io/)
[![Code complexity: radon](https://img.shields.io/badge/code%20complexity-radon-brightgreen)](https://radon.readthedocs.io/)
[![pytest: 100% coverage](https://img.shields.io/badge/pytest-100%25%20coverage-brightgreen)](https://pytest.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Disciplined Python patterns for catching bugs that type checkers and
standard linters miss — inspired by safety-critical coding guidelines from
other languages, adapted for a language and ecosystem they were not written
for.

## The problem, in one example

The Mars Climate Orbiter was lost because two teams silently
disagreed about units. The code for that class of bug still compiles
and passes mypy today.

```python
Thrust = NewType("Thrust", float)
FuelMass = NewType("FuelMass", float)

def compute_burn_time(*, thrust: Thrust, fuel_mass: FuelMass) -> float:
    ...

# Both floats. Nothing about a bare float stops this from compiling,
# type-checking cleanly, and silently swapping the two values.
compute_burn_time(thrust=fuel_mass, fuel_mass=thrust)
```

This is pyrigor’s PYR201 rule, `NewType` for same-typed values at
risk of being swapped. It is documented today, not yet enforced.
What pyrigor already catches, right now:

```bash
$ pyrigor launch_sequence.py
launch_sequence.py:12:1: PYR402 Function 'compute_burn_time' has
positional parameters; all parameters should be keyword-only
(keyword-only-arguments)
```

## Usage

```bash
pip install pyrigor
pyrigor path/to/file.py [path/to/another.py ...]
```

PYR301, PYR401, PYR402, PYR403, and PYR405 are enforced today. A violation
exits non-zero and prints `path:line:col: PYR40x message (symbolic-name)`.

To suppress a specific violation, add a same-line comment with a
reason:

```python
def f(weight, bias):  # pyrigor: PYR402 # matches a fixed external API
    ...
```

Codes may be given as the full code (`PYR402`), the bare number
(`402`), or the rule’s symbolic name (`keyword-only-arguments`).
Multiple codes: `# pyrigor: 402,403 # reason`. A suppression comment
without a reason is ignored, and a warning is printed. Suppressed
violations are counted per rule in the summary (`PYR402: 1
suppressed`), not silently discarded.

## What this is

Python’s failure modes are often silent: implicit type coercion,
positional-argument swaps between same-typed parameters, mutable default
arguments, float equality checks, and tuple-unpacking that "type-checks"
while being semantically wrong are all real, tool-catchable classes of
bugs that slip past mypy, pylint, and ruff’s default rule sets.

`pyrigor` collects a set of guidelines — and, over time, tooling to enforce
them — aimed at closing those gaps.

## Status

Early stage. As of mid 2026, five rules are implemented and enforced
(PYR301, PYR401, PYR402, PYR403, PYR405). Nine more are documented but
not yet enforced.

- [x] Guideline documentation
- [x] Standalone AST-based checkers (pre-commit local hooks) — PYR301,
  PYR401, PYR402, PYR403, and PYR405 are implemented. PYR201, PYR202,
  PYR203, PYR204, PYR205, PYR302, PYR404, PYR501, PYR502 are documented
  but not yet enforced.
- [ ] pylint plugin

## Guidelines

See [`guidelines/`](./guidelines) for the full list. Each guideline has a
rule ID, rationale, example, and — once implemented — a link to its
enforcing check.

Guidelines documented so far:

| ID     | Rule                                                                    | Enforced by                     |
|--------|-------------------------------------------------------------------------|---------------------------------|
| PYR201 | Use `NewType` for same-typed values at risk of being swapped            | Not yet implemented             |
| PYR202 | Use `Enum` instead of magic strings, ints, or bools for closed states   | Not yet implemented             |
| PYR203 | Use `Final` named constants for any number other than `0`, `1`, or `-1` | Not yet implemented             |
| PYR204 | Never compare floats with `==`; use tolerance-based comparison          | Not yet implemented             |
| PYR205 | Use a `Final` constant for a numeric literal duplicated in a file       | Not yet implemented             |
| PYR301 | Use `NamedTuple` instead of a bare fixed-length `tuple` type            | `pyrigor` CLI (pre-commit hook) |
| PYR302 | Use `frozen=True` for dataclasses holding structured state              | Not yet implemented             |
| PYR401 | Use `NamedTuple` for any function returning more than one value         | `pyrigor` CLI (pre-commit hook) |
| PYR402 | Force keyword-only arguments for 2+ function parameters (bare `*`)      | `pyrigor` CLI (pre-commit hook) |
| PYR403 | Force keyword-only arguments for single-parameter functions             | `pyrigor` CLI (pre-commit hook) |
| PYR404 | Use immutable default argument values, never mutable ones               | Not yet implemented             |
| PYR405 | Use `NamedTuple` for multi-value parameter types, not bare `tuple`      | `pyrigor` CLI (pre-commit hook) |
| PYR501 | End a `match` over a closed set with `case _: assert_never(...)`        | Not yet implemented             |
| PYR502 | State implicit input assumptions as explicit `assert` preconditions     | Not yet implemented             |

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

1. Browse or open an issue on [GitHub Issues](https://github.com/jarl-hoyem/pyrigor/issues)
2. Adding a new rule? Follow [`guidelines/ADDING_A_RULE.md`](./guidelines/ADDING_A_RULE.md) step by step.
3. Run `pre-commit run --all-files` before pushing.
4. Open a Pull Request.

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for full setup and workflow details.

## Contact

Maintained by [jarl-hoyem](https://github.com/jarl-hoyem). For
questions or ideas, open an issue.

## License

MIT
