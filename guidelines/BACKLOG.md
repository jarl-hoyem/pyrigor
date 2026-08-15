### PYR406: Disallow ignoring a required return value (reserved, not yet written up)

Like C++'s `[[nodiscard]]` or Rust's `#[must_use]`. A function’s
return value being silently discarded, called as a bare statement,
is very likely a bug if that return value is meaningful, `x = f()`
intended, `f()` written by mistake. Cannot be detected by inference
alone, same lesson as the mistake for PYR203 originally. Most discarded
return values are entirely intentional (`print(...)`,
`logging.info(...)`, `list.append(...)`). Needs an explicit marker
the developer applies, a decorator most likely, then a mechanical
check that a decorated function is never called as a bare expression
statement.

Real, independent precedent: OSSF’s Secure Coding Guide for Python,
pyscg-0036 ("Check Return Values"), cites MITRE CWE-252 (Unchecked
Return Value) and equivalent SEI CERT rules for Java (EXP00-J) and C
(EXP12-C). Worth citing directly when the full guideline doc is
eventually written, real, credible corroboration, not just an
analogy to C++/Rust.

Overlap check (`ADDING_A_RULE.md` step 0) not yet confirmed against
ruff or pylint.

## Future tooling ideas

### Full summary report (`--report`)

Three related, separate ideas that belong together:

- **Suppression audit report.** `filter_suppressed` already parses
  an optional free-text reason from `# pyrigor: CODE # reason`
  comments, captured but not surfaced anywhere. A report command
  could walk a codebase, collect every active suppression comment
  and its reason, and output a summary, useful for a team lead
  reviewing what is being silenced and why, the same way an old,
  unreviewed `# noqa` comment tends to accumulate unexamined on
  larger codebases.
- **Fuller violation reporting.** Per-rule and per-file violation
  counts, and per-rule suppression counts, already shipped. Worth
  extending: most-violated files, the most common rule, trend over
  time if run repeatedly.
- **Distinguishing "unadopted convention" rules from "avoidable
  footgun" rules in the report itself.** Found while running pyrigor
  against mypy’s own codebase: PYR402 and PYR403 fired thousands of
  times, high counts that mostly reflect a community-wide convention
  (bare `*` for keyword-only arguments) essentially no pre-existing
  codebase has adopted, not carelessness. PYR301, PYR401, and PYR405
  fired far less (3, 225, and 24 respectively across 441 files), a
  more genuinely meaningful signal, since these catch a specific,
  well-known, avoidable bug rather than an unadopted stylistic
  choice. A low count in the second category is real evidence of
  deliberate discipline, a low count in the first mostly is not.
  Worth surfacing this distinction in the report rather than
  presenting every rule’s count with equal weight.

Not yet designed as one feature. Would likely need its own CLI
subcommand (separate from the per-checker `main()` entry points) and
its own output format, deliberately out of scope for the initial
suppression mechanism and per-rule breakdown themselves.

### Structured argument parsing (scoped)

Replace run()’s hand-rolled argv parsing (bare "--version" in
sys.argv check, manual --only= prefix-match-and-mutate) with
argparse, standard library, no new dependency.

Concrete plan:

- `--version`, `-V`: existing behavior (print version, exit 0).
- `--only`: same value, comma-separated string, parsed the same way
  after argparse hands it over (argparse does not natively split
  comma-separated values, that parsing stays custom either way).
- Remaining positional arguments: `paths` (nargs="+" or nargs="*"
  since checking with no path is an arguably invalid input).

Real wins, not just style: free --help text, automatic rejection of
unrecognized flags (`--onl=PYR401`, a typo, silently gets
treated as a path and matched against nothing, no error at all),
consistent, and `--flag=value` support.

Real cost: every existing test calling run() via monkeypatched
sys.argv needs re-verifying against argparse’s own error-exit
behavior (argparse calls sys.exit(2) directly on a parse error,
different from this project’s own exit-code convention of 2 meaning
"crashed," worth deciding whether that collision matters or is
actually fine since both mean "did not run correctly").

Not urgent with only two flags today, worth doing before a third
flag (`--report`, already speculative in the full-summary-report
backlog item) makes the hand-rolled approach genuinely painful.

### Proper `.gitignore`-aware file discovery

`_collect_python_files()` currently uses a small hardcoded exclude
list (`.venv`, `.git`, `__pycache__`, `node_modules`, ...) when
walking directories, rather than respecting the repo’s actual
`.gitignore`. Good enough for now — the goal was avoiding wasted
time/noise on vendored or generated code, not building a general
file-discovery engine. Worth revisiting if the hardcoded list proves
not enough in practice (a real project with unusual excludes not on
the default list), or once there is a concrete reason to match `git
ls-files`/`.gitignore` semantics exactly.

### Per-rule directory/file excludes

Right now, excluding a path from pyrigor entirely means excluding it
at the pre-commit level (`exclude: ^tests/` in
`.pre-commit-config.yaml`) — all-or-nothing across every rule. A more
precise mechanism would let a project exclude specific rules from
specific paths (for example, "PYR402 does not apply under `tests/`, but PYR401
still does"), like ruff's `per-file-ignores`. Not yet designed. Would likely
live in a project-level pyrigor config file (`pyproject.toml` section,
or a dedicated config file), which does not exist yet.

### Detect unnecessary suppression comments

The tool mypy (and other type checkers) can flag a `# type: ignore` that’s no
longer suppressing anything, because the underlying issue was fixed,
and the suppression became dead weight. The tool pyrigor’s suppression comments
have the same problem: a `# pyrigor: CODE # reason` sitting on a line
that no longer actually violates that rule (because the code changed,
or the rule’s logic changed) is not flagged as unnecessary —
it just silently does nothing forever. Worth detecting and warning on
stale/unnecessary suppressions, the same way `filter_suppressed`
already warns on malformed or missing-reason ones.

### `--version` flag

The `pyrigor` CLI has no way to report its own installed version —
found while trying to confirm, which pyrigor version was installed in
a separate downstream project (`uv pip show pyrigor` was the
workaround). Small, standard, and genuinely useful once pyrigor is
used across multiple projects. Should be quick to add whenever
picked up — likely just a `--version`/`-V` flag in `run()` that reads
the installed package’s own version and exits, without needing to
touch `main()`'s actual checking logic.

### Changelog draft generator

`publish.yaml` could write the real release date into `CHANGELOG.md`
automatically, reading `github.event.release.published_at` and
replacing the matching version heading's `TODO`. Small, mechanical,
worth doing whenever picked up.

Generating the actual content is a different, harder problem, not
worth doing the same way. A tool that dumps every commit message
since the last tag tends to produce a noisy, unhelpful changelog,
especially given this project’s own commit messages are often long
and detailed for their own sake, not written as changelog-ready
one-liners. A better middle ground: since commit messages already
follow Conventional Commits (enforced by the `commitizen` hook), a
script could group commits by type (`feat`, `fix`, `docs`, `chore`)
since the last tag and generate a draft `CHANGELOG.md` section,
reviewed and trimmed by hand before a release rather than written
from scratch. Real, buildable, but a genuinely new tool, not a small
addition.

### The tool mutmut is unusable, both in CI and locally

Confirmed tonight: mutmut fails with the same FileNotFoundError
(copy_src_dir attempting to copy unrelated system files, for
example, /usr/share/doc/perl/Changes.gz) on a fresh Windows Subsystem
for Linux (WSL) installation, a
completely different environment from the GitHub Actions runners
where this was first found, and the job disabled. This confirms the
bug is in mutmut itself (its copy_src_dir walking too broad a root
directory), not specific to CI runners as originally assumed.

Not usable until this is fixed upstream, or a workaround is found
(possibly a narrower source paths config, already scoped to
pyrigor/ in pyproject.toml, worth checking if that scoping is
actually being respected by a copy_src_dir or ignored). Worth checking
mutmut’s own issue tracker for this exact FileNotFoundError before
assuming pyrigor’s own config is at fault.

The original "run it locally on pre-push, not just CI" idea is moot
until this underlying bug is resolved either way.

### Review tool exemptions carried over from Pickomino

Several tool-level exemptions, exclusions or ignored rules in
`.pre-commit-config.yaml` and `pyproject.toml` were copied directly
from Pickomino’s own config as a starting template, not re-evaluated
for whether they actually apply to pyrigor. Worth a deliberate pass
checking each one against pyrigor’s own codebase and needs, rather
than carrying Pickomino-specific exceptions forward by default.

### A Rust implementation for a single file or module

Explicitly a learning exercise, not a performance need (see
`PERFORMANCE.md`'s own reasoning for why a full Rust rewrite is not
justified now). Worth trying on one small,
self-contained
module first, to learn the shape of a Python/Rust boundary (`PyO3`
or similar) before considering anything larger.

### Rule: No variable names without vowels

A readability rule, `wrd` or `cnt` where `word` or `count` would be
clear. Needs a real design decision on scope and exceptions
(genuine abbreviations, loop indexes) before it could avoid being
noisy the way an early, unscoped magic-number rule would have been.

### Rule: No variable names under four characters, with exceptions

In the same category as the vowel rule, a readability constraint, not a
correctness one. Needs the exception list worked out carefully,
loop counters (`i`, `j`), coordinates (`x`, `y`) and common,
well-understood short names would need explicit carve-outs, or this
would be noisy on real code.

### Adoption guide split: New project versus legacy codebase

The current README and CONTRIBUTING content assumes a reader
starting fresh. A real legacy codebase adopting pyrigor for the
first time has a very different experience, hundreds or thousands
of pre-existing violations, likely needing a gradual, per-rule
rollout strategy. Adopt one rule, fix it, add the next rather than
turning on all rules at once. Worth a dedicated adoption guide
covering both paths.

### A static pyrigor badge, like ruff’s own

Scoped: a plain static shields.io badge, no dynamic data, no
hosting, matching ruff’s own badge in this README, which is also
purely static, for example
`https://img.shields.io/badge/checked%20with-pyrigor-blue`. Effort
is trivial, deciding wording and color, adding a copyable Markdown
snippet to CONTRIBUTING.md, or the README for adopting projects to
use. Still gated on having a real adopting audience for the badge to
matter to.

### A dynamic pyrigor status badge

A per-project badge reflecting real findings (violation count,
pass/fail), the way a CI-status badge does. A genuinely different,
larger feature from the static badge above would need real GitHub
Action infrastructure in each adopting project to generate a JSON
endpoint shields.io can read. Not scoped, not designed. Worth
revisiting only once the static badge exists and there is real
demand for something richer.

### Summary output inconsistency: Violation counts lack a label, suppression counts do not.

Found on the actual CLI output: the per-rule breakdown prints bare
counts (`PYR401: 5, PYR402: 92`), no label distinguishing what the
number means, while the suppression breakdown appends "suppressed"
to each count (`PYR402: 1 suppressed`). A reader glancing at the
per-rule line alone has to infer "violations" from context. The
suppression line is self-explanatory. Worth a consistent label on
both, for example, "Violations:" as a header line before the per-rule
breakdown, matching the clarity the suppression line already has.

### CLI flag to filter, which rules run: `--only`

Design worked out, not yet applied. `pyrigor --only PYR301,PYR401
path` should run and report only the specified rules, filtering
`CHECKERS` before the checker loop, rather than running everything
and discarding unwanted output. Multiple rules comma-separated, one
flag, matching the suppression comment’s own convention. Should
accept the same lenient forms suppression comments already do, full
code, bare number, or symbolic name, not just the full `PYRxxx` form.

Found genuinely useful while comparing pyrigor’s own findings
against real public style guides (Google’s Python Style Guide in
particular), wanting to isolate one rule’s results against a large
repo without the other four rules’ output in the way.

Needs `main()` itself to accept an optional filter set, not just
`run()` parsing argv, since `main()` is what actually knows about
`CHECKERS`. First test drafted:

```python
def test_main_only_runs_specified_rule(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """With only={"PYR401"}, only PYR401 violations should be reported, even if others exist."""
    (tmp_path / "bad.py").write_text(
        "def one(a, b):\n    ...\n\ndef two() -> tuple[int, int]:\n    ...\n"
    )

    main(paths=[str(tmp_path)], only={"PYR401"})

    captured = capsys.readouterr()
    assert "PYR401" in captured.out
    assert "PYR402" not in captured.out
```

### OSSF Secure Coding Guide for Python, a broader review worth doing.

https://github.com/ossf/wg-best-practices-os-developers/tree/main/docs/Secure-Coding-Guide-for-Python
A real, structured, numbered guideline set (pyscg-NNNN), similar in
spirit to pyrigor’s own PYRxxx documents, compliant/noncompliant
example code per rule. Only three of its ~15+ guidelines were
checked today (numbers section, coding-standards section). Worth a
fuller pass across all ten sections (encoding, neutralization,
exception handling, logging, concurrency, cryptography included) for
further overlap or corroboration, given how directly relevant the
three checked so far turned out to be.

### Rule: `not x` / truthiness check a NamedTuple or dataclass is almost always wrong.

Found live today: `filter_suppressed`'s return type changed from a
bare `list[Violation]` to `SuppressionResult(kept, suppressed)`, a
`NamedTuple`. Every existing `assert not result` silently kept
compiling and kept meaning something, just the wrong thing — a
2-element `NamedTuple` is never falsy regardless of its contents, so
`not result` always evaluates `False`, always failing, but for a
completely different reason than the test intended to check.

This is a real, checkable pattern: `not x` or `if x:` on a value
statically known to be a `NamedTuple` or `dataclass` instance (not a
`bool`, not a container) is seldom the actual intent, since
these types do not override truthiness and default to always-truthy.
Structurally like to PYR301/401/405’s own concern — a refactor
silently changes behavior with no error —, but the trigger here is a
truthiness check against a structured type, not a bare tuple
annotation. Not yet numbered or scoped. Needs its own design pass on
how to detect "this name is bound to a NamedTuple/dataclass instance"
reliably via AST alone before it is tractable to build.

### Auto fix for PYR402/PYR403

The only rules where auto fix is genuinely tractable: inserting `*,`
before the first parameter is fully mechanical, no judgment involved
in what the fix is. Every other current rule (PYR301/401/405, needs
invented names for a new NamedTuple and its fields. PYR203/205, needs
a meaningful constant name) requires real judgment a tool cannot
supply, and auto generating placeholder names would produce worse
code than the violation it replaced.

Real complication even for PYR402/PYR403: changing a signature this
way breaks every existing positional caller, unlike a formatter’s
fix, which is behavior-preserving by construction. Needs a design
decision: rewrite every call site to the keyword form too (much more
invasive, closer to a real refactoring tool than a linter), or only
fix the signature and let resulting TypeErrors at call sites surface
the remaining work. Given the earlier documented caution about
`ruff --fix` "messing everything up," worth treating any auto fix
here as opt-in and clearly scoped, not a default behavior.

### Investigate three specific dead-code detectors: Culler, uncalled, dead

The tool vulture is already in pre-commit. Worth specifically investigating
three named alternatives: Culler, uncalled, and dead. Not
independently verified to exist under these exact names, worth
confirming each first, then comparing detection approach,
false-positive rate, and whether any catches something vulture’s own
heuristics (confidence-scored, import-usage-based) miss.

### Definition of Ready

Companion to `DEFINITION_OF_DONE.md`. Before starting work on
something (a rule, a feature), what needs to be true first, is the scope
clear, overlap checked (per `ADDING_A_RULE.md` step 0), a number
reserved (per `NUMBERING.md`), for a rule specifically. Not yet
written. Worth checking whether Pickomino’s own DoR content (deferred
process, not adopted, per the CONTRIBUTING.md rewrite) has anything
worth reusing now this project has grown enough to want it.

### README duplication when adding a new rule

Adding a rule means updating the guideline table in
the README.md by hand, a real, repeated source of drift (found stale
multiple times this session: PYR401/PYR403/PYR405 all shown as "not
enforced" after they were). Directly connects to the single source
of truth architecture already deferred (generate the table from
rules.py + CHECKERS rather than hand-maintaining it). The same fix
closes both this and the next item.

### Rule list as a separate document

Related to the above: the guideline table lives inside
README.md itself. Worth considering whether it should be a separate
generated file (`guidelines/RULES.md` or similar), README linking to
it, rather than embedding a large, frequently stale table directly
in the project’s front door.

### Proper citations in rule docs

Rule docs cite sources informally, prose mentioning
"Steve McConnell’s *Code Complete*" or "Google’s Python Style Guide"
inline. Worth a consistent, structured citation format per rule
(book / article / talk / podcast, with a link where one exists), so
a third party can verify the claim independently, rather than taking
the doc’s word for it. PYR203 (McConnell), PYR401 (Google’s guide,
now cited inline), and PYR406 (OSSF’s pyscg-0036, cited inline) are
the existing candidates to retrofit into whatever format gets chosen.

### Rule: Flag an old/unsupported Python version

Not yet scoped. Needs a design decision: check `requires-python` in
pyproject.toml against current CPython End of Life status (external, changes
over time, same problem PYR301’s own numbering scheme had to solve
for pyrigor’s own supported-version policy), or check for
version-gated syntax/imports actually used in the code that implies
an old floor. Two different checks, worth deciding,
which, or both, before writing a guideline doc.

### Rule: Ban "_and_" in function names

A real, checkable naming smell, a function named `validate_and_save`
usually means it does two things and should be split into two
functions, the name admitting it via the literal word "and." Cheap,
structural (search identifier names for the substring), likely low
effort. Needs the same overlap check as any other rule (step 0)
before assuming it is a genuine gap.

### A sourcing list for future rules

A running list of books, articles, talks, podcasts, organizations,
and people worth mining for future rule ideas, plus famous bugs
worth citing as motivating examples (the Mars Climate Orbiter
example already used in the README’s own demo section). Distinct
from the BACKLOG.md’s own rule ideas, this is a list of *where to look*,
not ideas themselves. Candidates already surfaced this session:
Steve McConnell (Code Complete), Google’s Python Style Guide, OSSF’s
Secure Coding Guide for Python, PEP8, Django’s coding style
(checked, found silent), Clean Code (flagged as contested, not yet
independently verified), MicroPython/CircuitPython documentation (embedded Python
subset restrictions, see the separate entry on this).

### Rejected rules should not consume the PYRxxx number space

Rejecting a rule (per `REJECTED.md`) leaves its number
unused but implicitly reserved, since nothing else can claim it.
Given ruff alone has 900+ rules, systematically
checking pyrigor’s own future ideas against all of them and rejecting
matches would burn through the PYRxxx numbering scheme fast, for
rules that were never actually built. Worth a separate namespace for
rejected-and-therefore-never-registered rules, for example
`PYREJECT101`, so `REJECTED.md`'s own entries do not compete for the
same limited number space as real, built, or documented rules.

### Research rules for memory safety / no garbage collection

Flagged as needing real scoping before it is tractable, not assumed
practical. Python always uses garbage collection at the language
level, a rule cannot ban GC the way a systems-language linter might.
Worth researching what "memory safety" concerns actually translate
to Python (context manager discipline, resource cleanup,
reference cycles, weak references) versus what is a category
borrowed from C/Rust/embedded contexts that does not map over at all.
Do the overlap check (`ADDING_A_RULE.md` step 0) once any candidate
is identified, since resource-management linting already has some
coverage in existing tools.

### Reproducible run times for PERFORMANCE.md

`PERFORMANCE.md` already flags real variance from OS-level file
caching (34.30 s versus 18.86 s on back-to-back identical runs). Worth a
real methodology: run each configuration multiple times, discard the
first (cold cache) run, report the median or average of the rest,
rather than a single number that may be dominated by caching noise.

### Large Language Model supported bulk-fixing pyrigor findings as a bug-finding technique.

Speculative, not tested. Hypothesis: running pyrigor against a real
repo, then asking a Large Language Model (LLM) to fix every finding (in a copy of the
repo, not the real one), could surface real, pre-existing bugs as a
side effect, not because pyrigor detects them directly, but because
*fixing* certain findings forces the close reading pyrigor itself
never does.

Reasoning: pyrigor’s own detection is purely structural, it never
inspects what values are actually passed at a call site. But fixing
a PYR401 or PYR301 violation cannot be done as a pure syntax
transform, converting `return a, b` into a NamedTuple requires
finding and rewriting every unpacking call site, which means reading
what each site actually does with the values. That is the same
mechanism by which the project’s own original w/b swap bug would
have been caught, not detected by a linter, but noticed by someone
forced to look carefully during a refactor. PYR402/PYR403 are weaker
candidates for this, since they can often be fixed as pure syntax
insertion (`*,`) without touching call sites at all, where existing
callers already use compatible keyword calls.

Real risk, not just upside: an LLM doing this without being
explicitly asked to flag anomalies could silently
"fix" a real bug by guessing a plausible order, destroying the
evidence rather than surfacing it. Whether this works as a
bug-finding technique depends entirely on the fixing process being
asked to report anything suspicious, not just make tests pass.

Distinct from the existing auto fix backlog item, which is scoped as
mechanical (insert `*,`), not an LLM applying real comprehension.

Worth an actual small-scale test later: pick a real cloned repo
already on disk (Home Assistant, abseil-py), a batch of real PYR401
findings, and see whether anything surfaces.

### MicroPython/CircuitPython restrictions as a source of rule ideas

Both are constrained Python subsets for embedded targets, with real,
documented restrictions on what standard Python features are safe or
supported (limited dynamic behavior, restricted stdlib, memory
constraints). Worth reviewing their own documentation as a source of
rule ideas, the same way Code Complete, Google’s style guide, and
OSSF’s Secure Coding Guide were mined tonight. Not yet reviewed.

### Real, profiled performance bottleneck. The ast walk is called once per checker instead of once per every file.

Profiled against Home Assistant core with cProfile
(`python -m cProfile`), 18,187 files, 388 seconds total. The  `ast.walk` accounts
for 286 of those seconds cumulative, called
69,393,100 times, once independently per checker per every file (5
checkers x 18,187 files), each walking the same already-parsed tree
from scratch.

The earlier shared-parse refactor correctly fixed parsing the source
once per every file, but `find_function_violations` and
`find_assign_violations` each still call `ast.walk(tree)`
independently. A single shared walk per every file, collecting nodes into
flat `(function_nodes, assign_nodes)` lists once and handing the
same lists to every checker, would cut the dominant cost by
5x, since every checker already filters the walk’s output by
`isinstance` afterward regardless.

Raw profile output is kept for reference:

```
925169286 function calls (925168628 primitive calls) in 391.356 seconds
Ordered by: cumulative time

ncalls  tottime  percall  cumtime  percall filename:lineno(function)
18187    2.924    0.000  388.032    0.021 cli.py:110(_check_file)
18187    1.504    0.000  349.200    0.019 cli.py:82(_run_checkers)
69393100   45.657    0.000  286.112    0.000 ast.py:386(walk)
69302165   34.969    0.000  230.095    0.000 collections.deque.extend
54561   16.531    0.000  198.403    0.004 _shared.py:103(find_function_violations)
138513395   93.896    0.000  195.126    0.000 ast.py:280(iter_child_nodes)
182520705   51.826    0.000   73.510    0.000 ast.py:268(iter_fields)
```

### The pyproject.toml’s [tool.*] sections also have no deliberate order.

Same issue already logged for .pre-commit-config.yaml’s hook order,
confirmed present here too: [tool.mypy], [tool.ruff],
[tool.pytest.ini_options], [tool.coverage.run], [tool.pydocstyle],
[tool.mutmut], [tool.pylint.format], [tool.bandit],
[tool.bandit.assert_used], [tool.codespell] appear in whatever order
they were added, not alphabetically, not grouped by the category (type
checking, linting, testing, security), and not matching
.pre-commit-config.yaml’s own hook order either. Worth reordering
both files consistently in the same pass, since they describe
overlapping tooling, and a reader benefits from matching structure
between them.
