# pyrigor

[![PyPI version](https://img.shields.io/pypi/v/pyrigor.svg)](https://pypi.org/project/pyrigor/)
[![Downloads](https://static.pepy.tech/badge/pyrigor)](https://pepy.tech/project/pyrigor)
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
[![Cognitive complexity: complexipy](https://img.shields.io/badge/cognitive%20complexity-complexipy-brightgreen)](https://github.com/rohaquinlop/complexipy)
[![pytest: 100% coverage](https://img.shields.io/badge/pytest-100%25%20coverage-brightgreen)](https://pytest.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![actionlint](https://img.shields.io/badge/GitHub%20Actions-actionlint-brightgreen)](https://github.com/rhysd/actionlint)
[![Security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![Dead code: vulture](https://img.shields.io/badge/dead%20code-vulture-brightgreen)](https://github.com/jendrikseipp/vulture)
[![codespell](https://img.shields.io/badge/spelling-codespell-brightgreen)](https://github.com/codespell-project/codespell)
[![Checked with pyrigor](https://img.shields.io/badge/checked%20with-pyrigor-blue)](https://github.com/jarl-hoyem/pyrigor)

Catches the class of bug type checkers structurally cannot: a
NamedTuple/keyword-only-argument/return-value-usage rule set for
Python, inspired by safety-critical coding guidelines from other
languages.

- Enforced rules catching real, silent bugs mypy strict mode passes
  clean
- Validated against real, public codebases: CPython's stdlib, Home
  Assistant, mypy, requests, hypothesis, abseil-py
- Checks an 18,187-file real-world codebase in under a minute
- Drop-in pre-commit integration, or run standalone

## Table of Contents

- [The problem, in one example](#the-problem-in-one-example)
- [Usage](#usage)
- [Adding pyrigor to your own project](#adding-pyrigor-to-your-own-project)
- [What this is](#what-this-is)
- [Status](#status)
- [Guidelines](#guidelines)
- [Philosophy](#philosophy)
- [Contributing](#contributing)
- [Acknowledgements](#acknowledgements)
- [Contact](#contact)
- [License](#license)

## The problem, in one example

The Mars Climate Orbiter was lost because two teams silently
disagreed about units. The code for that class of bug would still
get past mypy today.

```python
Thrust = NewType("Thrust", float)
FuelMass = NewType("FuelMass", float)


def compute_burn_time(*, thrust: Thrust, fuel_mass: FuelMass) -> float: ...


# Both floats. Nothing about a bare float stops this from running,
# type-checking cleanly, and silently swapping the two values.
compute_burn_time(thrust=fuel_mass, fuel_mass=thrust)
```

This is pyrigor's PYR201 rule, `NewType` for same-typed values at
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

Every rule marked enforced in [`guidelines/RULES.md`](./guidelines/RULES.md)
runs automatically. A violation exits non-zero and prints
`path:line:col: PYRxxx message (symbolic-name)`.

Run `pyrigor --version` to check the installed version.
Use `--select=CODE,CODE` to restrict checking to specific rules, for
example `pyrigor --select=PYR401,keyword-only-arguments path/`. Use
`--ignore=CODE,CODE` to exclude specific rules instead, running
every other one. Both may be combined — `--ignore` removes codes
from `--select`'s set (or from every rule, if `--select` is
omitted). The codes may be given as the full code, the bare number,
or the symbolic name, the same as suppression comments. An
unrecognized code exits immediately with an error naming it, as does
a `--select`/`--ignore` combination that leaves no rules to check.
Use `--exclude PATH` to omit a file or directory and everything below it.
Repeat the option to exclude multiple paths. This exclusion is
applied by pyrigor itself, independently of any pre-commit file filter.

For the machine-readable editor or tooling integration, use
`--output-format=json`. It emits one JSON document containing diagnostics,
read/parse errors, and suppression counts. The default human-readable format
is unchanged. See [`guidelines/JSON_DIAGNOSTICS.md`](./guidelines/JSON_DIAGNOSTICS.md)
for the contract and schema.

To suppress a specific violation, add a same-line comment with a
reason:

```python
def f(weight, bias):  # pyrigor PYR402 # matches a fixed external API
    ...
```

Codes may be given as the full code (`PYR402`), the bare number
(`402`), or the rule's symbolic name (`keyword-only-arguments`).
Multiple codes: `# pyrigor 402,403 # reason`. A suppression comment
without a reason is ignored, and a warning is printed. Suppressed
violations are counted per rule in the summary (`PYR402: 1
suppressed`), not silently discarded.

When stacking with another tool's own suppression comment on the
same line (`# nosec`, `# complexipy: ignore`, ...), put pyrigor's
own comment last — `# nosec  # pyrigor PYR402 # reason`. Pyrigor's
own comment must come after any other tool's comment, since its reason
captures to the end of the line.

A suppression comment may also go on the line directly above the
violation, or anywhere within a multi-line statement's own span —
useful when a long, descriptive name plus the mandatory reason
would not fit on the violating line itself:

```python
# pyrigor PYR402 # long test names plus a mandatory reason need more room
def apply_correction_for_the_pytest_fixture_injection_case(weight, bias): ...
```

The same-line still works exactly as before — these are additional
locations, not a replacement. This flexibility is a deliberate design
advantage over tools like ruff or bandit, which require the suppression
comment to sit on the exact physical line of the violation, making it
easy to place incorrectly on wrapped statements. Pyrigor's suppression
works anywhere within the violation's span, so placement matters less.

## Adding pyrigor to your own project

Add pyrigor to your own `.pre-commit-config.yaml` as a pinned,
remote hook, the same way you would add `ruff` or `black`:

```yaml
- repo: https://github.com/jarl-hoyem/pyrigor
  rev: v0.12.0
  hooks:
    - id: pyrigor
      args: [ --exclude, generated ]
```

Pin `rev:` to a real, released tag, not `main`. Check the
[release page](https://github.com/jarl-hoyem/pyrigor/releases) for
the latest version.

Show it in your own README:

```markdown
[![Checked with pyrigor](https://img.shields.io/badge/checked%20with-pyrigor-blue)](https://github.com/jarl-hoyem/pyrigor)
```

## What this is

Python's failure modes are often silent: implicit type coercion,
positional-argument swaps between same-typed parameters, mutable default
arguments, float equality checks, and tuple-unpacking that "type-checks"
while being semantically wrong are all real, tool-catchable classes of
bugs that slip past mypy, pylint, and ruff's default rule sets.

`pyrigor` is a set of guidelines, with real, working tooling
enforcing them today, growing as more rules are built out.

## Status

Early stage.

See [`guidelines/RULES.md`](./guidelines/RULES.md) for the full,
generated list of every rule and whether it is enforced yet.

- [x] Guideline documentation
- [x] Standalone AST-based checkers (pre-commit local hooks)
- [ ] Editor integration (deferred until real demand exists, see #152)

## Guidelines

See [`guidelines/`](./guidelines) for the full list. Each guideline has a
rule ID, rationale, example, and — once implemented — a link to its
enforcing check.

[`guidelines/RULES.md`](./guidelines/RULES.md) has a generated table of
every rule and whether it is enforced yet — generated from the real
guideline docs and `CHECKERS`, never hand-maintained, so it cannot drift
the way this table once did.

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

Participation is governed by the [Code of Conduct](./CODE_OF_CONDUCT.md).

1. Every change starts with an issue. Check
   [open issues labeled `ready`](https://github.com/jarl-hoyem/pyrigor/issues?q=is%3Aissue+is%3Aopen+label%3Aready)
   for a well-scoped starting point, or open a new one.
2. Adding a new rule? Follow [`guidelines/ADDING_A_RULE.md`](./guidelines/ADDING_A_RULE.md) step by step.
3. Run `pre-commit run --all-files` before pushing.
4. Open a Pull Request.

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for full setup and workflow details.

## Feedback

Evaluating pyrigor for your own project? Open an
[issue](https://github.com/jarl-hoyem/pyrigor/issues) and tell me
about your use case — I use real adoption signals to drive priorities.

## Acknowledgements

The tool pyrigor's own rules draw directly on real, external sources, not
invented in isolation: Steve McConnell's *Code Complete*, the OSSF
Secure Coding Guide for Python, and Google's Python Style Guide.
Built on the shoulders of the real, open source tooling, it runs
alongside every day: ruff, pylint, mypy, pyright, and pytest, among
others credited throughout this project's own guideline docs.

## Contact

Created and maintained by [jarl-hoyem](https://github.com/jarl-hoyem). For
questions or ideas, open an issue.

## License

MIT
