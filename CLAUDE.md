# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`pyrigor` is a Python coding-discipline guideline collection and CLI linter.
Guidelines live in `guidelines/PYRxxx-*.md`. A subset is enforced today by
AST-based checkers under `pyrigor/checkers/`. It targets Python 3.11+ and is
dogfooded on itself (pyrigor’s own source must pass its own checks).

## Commands

Setup:

```bash
uv sync --extra dev
pre-commit install
```

Run the linter itself:

```bash
uv run pyrigor path/to/file.py [path/to/dir ...]
uv run pyrigor --only=PYR401,PYR402 path/     # restrict to specific rules (code, bare number, or symbolic name)
uv run pyrigor --version
```

Run tests:

```bash
uv run pytest                                              # full suite, 100% coverage enforced (--cov-fail-under=100)
uv run pytest tests/checkers/test_pyr402_keyword_only_arguments.py   # single file
uv run pytest tests/checkers/test_pyr402_keyword_only_arguments.py::test_name  # single test
uv run pytest -m slow                                       # slow tests are deselected by default
```

Run all quality gates (same checks CI runs via pre-commit, so there is no separate CI-only config to drift):

```bash
pre-commit run --all-files
```

`pytest` currently runs as part of this (no `stages:` restriction is active yet — the pytest hook in
`.pre-commit-config.yaml` has a commented-out `stages: [pre-push]` line, "saved for later," not yet applied).

Individual tools, if needed outside pre-commit: `uv run mypy .`, `uv run pyright --project=pyproject.toml`,
`uv run ty check .`, `uv run ruff check` / `ruff format`.

## Architecture

**Rule identity flows from one place.** The file `pyrigor/rules.py` defines the `Rule` enum. Each member’s value is a
`RuleInfo(symbolic_name, problem)`. A symbolic name (used in suppression comments and CLI output) and problem text
(used in violation messages) are declared once, here, not duplicated per-checker.

**Pipeline:** `cli.py` (`main`) collects `.py` files → parses each with `ast.parse` once → `checkers/_shared.py`'s
`walk_once()` walks the tree exactly once, splitting nodes into `WalkedNodes(function_nodes, assign_nodes,
call_statement_nodes, class_nodes)` for every checker to reuse → each registered checker's `find_violations(*, nodes:
WalkedNodes)` runs against those pre-walked nodes → `suppression.py`'s `filter_suppressed()` splits results into
kept/suppressed based on same-line
`# pyrigor: CODE # reason` comments → CLI prints and summarizes.

The single shared walk is a deliberate performance choice, not an accident — see `guidelines/DECISIONS.md` for why
a per-checker `ast.walk()` was replaced with this and why a caching alternative was rejected (walking scaled
linearly with checker count. Profiling against a large external codebase found `ast.walk` was the dominant cost).

**Checker registration is explicit and manual, on purpose.** `pyrigor/checkers/__init__.py`'s `CHECKERS` tuple
pairs each `Rule` member with its `find_violations` function by name (
`RegisteredChecker(rule=..., find_violations=...)`),
not by shared declaration order — a prior positional-coupling bug (`zip(CHECKERS, Rule)`) motivated this. A checker
that exists but is not added to `CHECKERS` silently never runs. This has happened before (see
`guidelines/ADDING_A_RULE.md` step 7).

**Violations** are built only via `pyrigor.violations.make_violation(node=..., rule=...)`, never constructed by hand,
so the message text cannot drift from the rule it is tied to.

**Suppression** (`suppression.py`) recognizes `# pyrigor: CODE[,CODE] # reason` on the violating line. The `CODE`
token may be the full code (`PYR402`), bare number (`402`), or symbolic name (`keyword-only-arguments`) — the same
three forms `--only` accepts. Any suppression without a reason is ignored (with a warning), not silently honored.

**Adding a new rule** is a defined, checklist-driven process — follow `guidelines/ADDING_A_RULE.md` step by step
(numbering bucket in `guidelines/NUMBERING.md`, naming convention in `guidelines/NAMING.md`). Key points that have
caused real bugs before: guideline-doc filename slug must exactly match the `Rule` enum's `symbolic_name`
(enforced by `tests/test_rules_docs_sync.py`). Check first whether ruff/pylint/mypy-strict already cover the pattern
before writing a rule (otherwise it goes in `guidelines/REJECTED.md`, not as a new rule).

## Approval before file changes

Every file change — Edit/Write calls, and any Bash/PowerShell command
writing to disk (`sed -i`, redirects, `git add`/`commit`, or similar) —
needs the user’s explicit go-ahead in chat first, with the concrete
diff or new content shown, not just a plan description. Applies
regardless of how small or mechanical the change looks. See
`~/.claude/settings.json`'s `permissions.ask` list for the
harness-enforced subset of this — Edit/Write always, plus specific
write-shaped Bash/PowerShell command patterns.

## Backlog and issue tracking

New work items go to GitHub Issues, not `BACKLOG.md` — the file
stays as-is, a historical archive of pre-existing items already
written up.

When starting work on an existing `BACKLOG.md` item, migrate it to
a GitHub issue first: copy the full write-up over, at full
fidelity, not compressed, then delete the entry from `BACKLOG.md`
entirely. Do not leave a pointer stub — git history already
preserves the original text. Treat the deletion as a required step
of the migration, not an afterthought. A forgotten deletion leaves
the item duplicated — live in the issue, still dormant in the
backlog — and at risk of being picked up a second time by mistake.

## Project-wide conventions

- All checker/CLI functions use keyword-only arguments (`*,`) — pyrigor enforces this on itself (PYR402/PYR403).
- Functions returning more than one value use `NamedTuple`, not bare tuples (PYR401) — see `guidelines/DECISIONS.md`
  for why `NamedTuple` and `NewType` close different gaps.
- Google-style docstrings (pydocstyle-checked) on public functions.
- 100% test coverage (branch included) is enforced on every commit, not aspirational.
- Before declaring any feature/fix done, apply `guidelines/DEFINITION_OF_DONE.md` and
  `guidelines/REVIEW_CHECKLIST.md` — both are living checklists earned by real defects that previously slipped
  through (for example, an untested edge case in `--only`'s lenient-form parsing), not generic boilerplate.
- Design/architecture *why*, not just *what*, belongs in `guidelines/DECISIONS.md`.
