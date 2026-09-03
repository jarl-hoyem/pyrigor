# CLAUDE.md

## Response formatting preference

When providing text intended for copying, put it in a fenced code block so the
user can copy it with one click.

The maintainer commits and pushes changes. The agent must never commit or push.
Do not begin work on an issue without explicit authorization. When reporting
validation, say “all tests” rather than emphasizing test counts.

Keep AGENTS.md and CLAUDE.md synchronized when changing repository guidance.

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`pyrigor` is a Python coding-discipline guideline collection and CLI linter.
Guidelines live in `guidelines/PYRxxx-*.md`. A subset is enforced today by
AST-based checkers under `pyrigor/checkers/`. It targets Python 3.11+ and is
dogfooded on itself (pyrigor's own source must pass its own checks).

## Commands

Setup:

```bash
uv sync --extra dev
pre-commit install
```

Run the linter itself:

```bash
uv run pyrigor path/to/file.py [path/to/dir ...]
uv run pyrigor --select=PYR401,PYR402 path/   # restrict to specific rules (code, bare number, or symbolic name)
uv run pyrigor --ignore=PYR406 path/          # exclude specific rules instead; combines with --select
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
just check
```

`pytest` currently runs as part of this (no `stages:` restriction is active yet — the pytest hook in
`.pre-commit-config.yaml` has a commented-out `stages: [pre-push]` line, "saved for later," not yet applied).

Individual tools, if needed outside pre-commit: `uv run mypy .`, `uv run pyright --project=pyproject.toml`,
`uv run ty check .`, `uv run ruff check` / `ruff format`.

Alternatively, use `just` — a simpler task runner — for copy-paste-runnable recipes:

```bash
just help     # List all available recipes
just check    # Run pre-commit
just test     # Run pytest
just pyrigor  # Run pyrigor
```

See the `justfile` in the repository root for the full set of recipes.

## Architecture

**Rule identity flows from one place.** The file `pyrigor/rules.py` defines the `Rule` enum. Each member's value is a
`RuleInfo(symbolic_name, problem, severity)`. A symbolic name (used in suppression comments and CLI output), problem
text (used in violation messages), and a severity (`Severity.ERROR`/`WARNING`/`INFO`, matching the Language Server
Protocol's own `DiagnosticSeverity` naming — see `DECISIONS.md`'s "Severity" entry) are declared once, here, not
duplicated per-checker.

**Pipeline:** `cli.py` (`main`) collects `.py` files -> parses each with `ast.parse` once ->  `checkers/_shared.py`'s
`walk_once()` walks the tree exactly once, splitting nodes into `WalkedNodes(function_nodes, assign_nodes,
call_statement_nodes, class_nodes)` for every checker to reuse -> each registered checker's `find_violations(*, nodes:
WalkedNodes)` runs against those pre-walked nodes ->  `suppression.py`'s `filter_suppressed()` splits results into
kept/suppressed based on same-line
`# pyrigor CODE # reason` comments -> CLI prints and summarizes.

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

**Suppression** (`suppression.py`) recognizes `# pyrigor CODE[,CODE] # reason` on the violating line. The `CODE`
token may be the full code (`PYR402`), bare number (`402`), or symbolic name (`keyword-only-arguments`) - the same
three forms `--only` accepts. Any suppression without a reason is ignored (with a warning), not silently honored.

**Adding a new rule** is a defined, checklist-driven process — follow `guidelines/ADDING_A_RULE.md` step by step
(numbering bucket in `guidelines/NUMBERING.md`, naming convention in `guidelines/NAMING.md`). Key points that have
caused real bugs before: guideline-doc filename slug must exactly match the `Rule` enum's `symbolic_name`
(enforced by `tests/test_rules_docs_sync.py`). Check first whether ruff/pylint/mypy-strict already cover the pattern
before writing a rule (otherwise it goes in `guidelines/REJECTED.md`, not as a new rule).

For every implementation change, build and run a deliberate test matrix:
normal behavior, edge and boundary cases, meaningful combinations, and
relevant negative or error paths. Never treat a passing happy-path test,
static analysis, or a vague request to "add a test" as evidence that the
matrix is complete. See `guidelines/DEFINITION_OF_DONE.md`.

## Economical agent workflow

Work efficiently with model tokens, tool calls, network access, and the
maintainer's time:

- Read only the issue-relevant code and documentation. Do not produce project
  overviews for the maintainer unless explicitly requested.
- Reuse context already gathered in the conversation. Do not refetch or
  restate it without a concrete reason.
- Batch a related read-only inspection into a few tool calls.
- Use the least expensive model tier likely to complete the task correctly:
  - Use an economy/fast model for mechanical edits, documentation
    synchronization, file reordering, straightforward tests, and known-pattern
    fixes.
  - Use a balanced general-purpose model for normal implementation, unfamiliar
    code paths, moderate debugging, and reviews requiring judgment.
  - Use a frontier model for challenging architecture, subtle semantics,
    hard-to-reproduce bugs, or security-sensitive review.
- Before starting a clearly mechanical task, recommend a cheaper model. State
  that only the user can switch the primary session's model. Delegated
  subagents may use a cheaper model when delegation is appropriate. Wait for
  the user's choice before proceeding.
- Increase model capability or reasoning effort only when task complexity or
  observed failure warrants it. Reserve the most expensive reasoning modes for
  work where their quality gain justifies the additional cost.
- Prepare one cohesive, exact diff for the approval instead of requesting a series
  of small edits.
- Use targeted validation proportional to the change. Do not duplicate the
  full pre-commit suite when the maintainer's commit workflow runs it,
  unless targeted checks reveal risk or the maintainer requests it.
- Always run `just check` after the final changes and before
  providing a commit message. Do not hand validation back to the maintainer
  unless a hook fails and its failure is reported explicitly.
- A passing `just check` does not guarantee a passing commit. It validates the
  working tree, whereas the commit-time hook stashes unstaged changes and
  validates staged content only. When those differ, the commit runs against
  something never tested. Always list every file the change needs alongside the
  commit message, so no file can be left out of the stage. A partial stage that
  splits a constant from the tests derived from it will fail at commit time
  while `just check` passes.
- Prefer public browser access for GitHub reads. Use authenticated CLI access
  only when the browser cannot retrieve required information.
- When the current GitHub state matters, explicitly refresh issue/PR data before
  answering. Do not rely on cached issue context. Confirm the repository state
  locally with `git status` and `git log -1`. If remote state matters, run
  `git fetch origin` first.
- Do not use subagents for small or sequential tasks.
- Keep progress updates brief and report only information that affects the
  task or requires a decision.
- The maintainer handles staging, commits, and pushes. Provide a
  copy-paste-ready commit message after verified file changes.
- Combine the approved closing comment and issue close into one GitHub action.
- Before release or issue work, reread this file, `AGENTS.md`, the relevant
  issue template, and applicable project guidance; do not rely on memory from
  another session.
- Validate commit messages against the repository's actual Commitizen
  configuration before recommending them; use only configured commit types.
- Treat `.pyscn/` reports as temporary output: remove them after inspection;
  do not commit or add them to `.gitignore`.

## Approval before file changes

Every file change — Edit/Write calls, and any Bash/PowerShell command
writing to disk (`sed -i`, redirects, `git add`/
`commit`, or similar) — needs the user's explicit go-ahead in chat first, with the concrete
diff or new content shown, not just a plan description. Applies
regardless of how small or mechanical the change looks. See
`~/.claude/settings.json`'s `permissions.ask` list for the
harness-enforced subset of this — Edit/Write always, plus specific
write-shaped Bash/PowerShell command patterns.

Before and after every file edit, preserve bytes outside the intended change.
Do not rewrite whole files through PowerShell or other text-mode tools. Use
byte-preserving patch operations, then verify the diff, encoding, line endings,
and mojibake markers. If byte preservation cannot be guaranteed, stop and ask.

After every file edit, run the relevant pre-commit checks. Fix any findings
before presenting the result.

A suppression comment (`# pyrigor CODE # reason`, `# pylint: disable=`,
`# type: ignore`, `# noqa`, or any equivalent) needs its own explicit
go-ahead, separate from the approval of the surrounding diff. Before adding
one, state what the tool is flagging, why fixing it directly is not the
better answer here, and the reason text the suppression will carry. Wait
for a clear yes before adding it.

Do not add `Co-Authored-By:` trailers to commit messages.

## Backlog and issue tracking

New work items go to GitHub Issues.

When creating a GitHub issue, always use the repository's issue template.
Preserve its headings and order. Do not substitute headings such as
"Acceptance criteria" for the template's "Done when" heading. If the
template cannot be found, inspect it before drafting the issue. Before
creation, verify the template headings, labels, milestone availability, and
required fields.

Blocking relationships between issues uses GitHub's native "blocked
by" feature, not prose "Blocked on #N"/"Blocks #N" text in the issue
body. Set it via the UI, or the `addBlockedBy` GraphQL mutation -
`gh issue`/`gh api` REST have no direct subcommand for it as of this
writing. It is a real, bidirectional, filterable relationship, not
just a citation. Older issues (#66/#67) still use the prose form
from before this convention started. Not worth migrating
retroactively. Use the real feature going forward.

Any GitHub issue action that changes its state — creating,
editing, commenting on, labeling, or closing an issue — needs the
user's explicit go-ahead first, the same as a file edit. Show what
will be created, changed, or said before doing it, not just
describe the plan.

Closing an issue always needs a closing comment summarizing what
shipped (the commit, what changed, what it resolves), even when the
issue was already closed by the time the comment goes up. A bare
close with no comment loses the "here is what actually happened"
record a reader would otherwise have to reconstruct from commit
history alone.

GitHub auto-closes an issue the moment a closing keyword (`fix`,
`fixes`, `closes`, `resolves`, and their variants) sits directly in
front of `#N` in any commit message that lands on the default
branch — no PR, no review, no repo setting to turn it off. This
bypasses the go-ahead-and-closing-comment rule above entirely,
silently: issue #10 was auto-closed this way by a commit titled
"fix: #10 repeated --only= errors, #12 ..., #20 ..., #30 ...", with
no closing comment, and it only came to light when asked why the
issue was already closed. A commit message should reference an
issue neutrally (`refs #10`, `part of #10`), not with a closing
keyword, unless closing it immediately as part of that same commit
is genuinely the intent — a closing keyword in a commit message
*is* the close action, not just a citation, and needs the same
go-ahead as calling `gh issue close` directly.

GitHub's scanner has no concept of quotation or descriptive context
either—it matches the literal text, full stop. Issue #11 was
auto-closed by a commit whose message *quoted* a wrong changelog
line ("v0.8.0's own CHANGELOG.md entry said, 'Closes #11,' but #11
was still open") specifically to explain why that line was wrong.
The quoted phrase alone was enough to trigger the same auto-close it
was describing as ineffective, with no closing comment, same as
#10. Quoting someone else's bad closing-keyword text, even to
correct it, needs the same care as writing one directly. Rephrase
the quoted reference (for example, "an entry claiming to close #11") or add
a zero-width break, rather than reproducing the exact keyword-then-#N
pattern verbatim.

## Project-wide conventions

- All checker/CLI functions use keyword-only arguments (`*,`) - pyrigor enforces this on itself (PYR402/PYR403).
- Functions returning more than one value use `NamedTuple`, not bare tuples (PYR401) - see `guidelines/DECISIONS.md`
  for why `NamedTuple` and `NewType` close different gaps.
- Google-style docstrings (pydocstyle-checked) on public functions.
- Write short documentation sentences that do not trigger PyCharm's
  sentence-length inspection. Prefer splitting sentences over using semicolons.
- Write prose in British English, using `-ise` spelling, so `normalise` and
  `recognise`. Python identifiers keep their own spelling, such as `normalize`
  and `serialize`. Do not change code to match prose.
- Use straight apostrophes and quotation marks. Never use the curly forms
  (U+2019, U+201C, U+201D). Google's and Microsoft's developer documentation
  style guides both require this. PyCharm's Grazie inspection suggests the
  opposite, and that inspection is deliberately switched off.
- Do not use em dashes (U+2014) or en dashes (U+2013). Split the sentence with
  a full stop or use a comma or parentheses. For a range, use a hyphen or the
  word "to."
- Do not use contractions. Write the expanded form, so "cannot" and "it is."
- Existing documentation does not yet follow these four rules. Issues #218 to
  #221 track the cleanup. Write new prose to the rules rather than imitating
  the surrounding text.
- Direct quotations are reproduced as the source wrote them. The rules above
  govern our own prose, not quoted text, so Knuth's "premature optimization
  is the root of all evil" in `guidelines/PRINCIPLES.md` keeps its American
  spelling. Never silently correct a quotation to house style. Where the
  original would breach a rule, paraphrase instead of quoting.
- Use LF line endings for all files (enforced via `.gitattributes`). Do not introduce mixed line endings.
- Run targeted formatting and lint checks before the full pre-commit suite, so it validates
  an already-clean working tree on its first run.
- Use byte-preserving operations for encoding or line-ending conversions.
  Verify the resulting bytes and text before finishing.
- 100% test coverage (branch included) is enforced on every commit, not aspirational.
- Before declaring any feature/fix done, apply `guidelines/DEFINITION_OF_DONE.md` and
  `guidelines/REVIEW_CHECKLIST.md`  - both are living checklists earned by real defects that previously slipped
  through (for example, an untested edge case in `--only`'s lenient-form parsing), not generic boilerplate.
- Design/architecture *why*, not just *what*, belongs in `guidelines/DECISIONS.md`.
