## Backlog index (value/effort at a glance)

| Item                                                                            | Value | Effort      |
|---------------------------------------------------------------------------------|-------|-------------|
| Full summary report (`--report`)                                                | M     | L           |
| Structured argument parsing (scoped)                                            | S     | M           |
| Proper `.gitignore`-aware file discovery                                        | S     | M           |
| Per-rule directory/file excludes                                                | M     | M           |
| Detect unnecessary suppression comments                                         | M     | M           |
| Changelog draft generator                                                       | S     | L           |
| mutmut unusable (blocked, upstream)                                             | —     | — (blocked) |
| Review tool exemptions carried over from Pickomino                              | S     | S           |
| A Rust implementation for a single file or module                               | XS    | L           |
| Rule: no variable names without vowels                                          | S     | M           |
| Rule: no variable names under four characters                                   | S     | M           |
| Adoption guide split: new project versus legacy                                 | M     | S           |
| A static pyrigor badge                                                          | XS    | XS          |
| A dynamic pyrigor status badge                                                  | S     | L           |
| Summary output inconsistency (missing label)                                    | S     | XS          |
| OSSF Secure Coding Guide, broader review                                        | M     | M           |
| Rule: truthiness check on NamedTuple/dataclass                                  | M     | L           |
| Auto fix for PYR402/PYR403                                                      | M     | L           |
| Investigate dead-code detectors (Culler, uncalled, dead)                        | XS    | S           |
| Definition of Ready                                                             | S     | S           |
| README duplication when adding a rule                                           | M     | M           |
| Rule list as a separate document                                                | S     | S           |
| Proper citations in rule docs                                                   | S     | S           |
| Rule: flag an old/unsupported Python version                                    | S     | M           |
| Rule: ban "_and_" in function names                                             | S     | S           |
| A sourcing list for future rules                                                | S     | S           |
| Rejected rules should not consume the PYRxxx number space                       | S     | XS          |
| Research rules for memory safety / no garbage collection                        | XS    | L           |
| Reproducible run times for PERFORMANCE.md                                       | S     | S           |
| LLM-assisted bulk-fixing as a bug-finding technique                             | S     | M           |
| MicroPython/CircuitPython restrictions as rule source                           | S     | S           |
| pyproject.toml `[tool.*]` section ordering                                      | XS    | S           |
| Harden pyrigor against bad user input                                           | M     | L           |
| Robustness against non-Python file content                                      | S     | S           |
| Rule: non-English identifiers                                                   | S     | L           |
| Rule: non-English comments                                                      | S     | M           |
| Apply the Pareto principle to backlog prioritization                            | S     | XS          |
| Review the backlog for split-worthy entries                                     | S     | S           |
| Identify and reach early adopters for pyrigor                                   | M     | M           |
| Formalize value-driven prioritization                                           | S     | S           |
| Derive rules systematically from the software "-ilities"                        | M     | S           |
| Group rules in documentation by the "-ilities" they serve                       | S     | S           |
| Add remaining useful pre-commit-hooks entries                                   | S     | XS          |
| Generate the project website automatically on release                           | M     | L           |
| Broader tool candidates to consider (batch, unresearched)                       | S     | M           |
| Make pyrigor discoverable (SEO)                                                 | M     | M           |
| Optimize pyrigor for LLM discoverability                                        | M     | S           |
| Keep a list of known, unfixed bugs                                              | S     | XS          |
| Solo-developer bottleneck: investigate how to speed up                          | L     | M           |
| Use every documented rule, not just enforced ones, to review the project itself | M     | L           |
| Add inline `#` comments explaining "why," not just docstrings                   | M     | M           |
| Track code-quality statistics (% code, % blank, % comments)                     | S     | S           |
| Support Read the Docs                                                           | M     | S           |
| Style-check newly added backlog entries                                         | XS    | XS          |
| Periodically review and prune BACKLOG.md                                        | S     | XS          |
| Second-order performance findings, post-walk-fix (minor)                        | XS    | S           |
| Real local-versus-CI drift found, despite pre-commit being the shared mechanism | S     | S           |
| Dependabot doesn't cover Python deps                                            | XS    | S           |
| PYR407 (reserved), discarding a generator call silently.                        | S     | M           |
| Optional astroid-based obj.foo() resolution, isolated experiment                | S     | M           |
| Submit CFP answers to Python conferences.                                       | L     | M           |
| Relax complexipy/xenon threshold to go from solo to collaborative development   | M     | S           |
| Review and deliberately set thresholds/settings for every pre-commit tool       | S     | M           |
| Run radon-maintainability and pyrigor’s own hook against tests/                 | M     | M           |
| Document every tool's own suppression-comment syntax in one place               | M     | S           |
| Migrate BACKLOG.md to GitHub Issues                                             | M     | M           |

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

Confirmed independently: mutmut fails with the same FileNotFoundError
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
multiple times already: PYR401/PYR403/PYR405 all shown as "not
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
not ideas themselves. Candidates already identified:
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
OSSF’s Secure Coding Guide were mined already. Not yet reviewed.

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

### Harden pyrigor against bad user input

A real, not-yet-systematic pass is needed across several input surfaces,
each with a different failure mode:

- **CLI arguments.** `--only` is now validated against known rule
  identities, but other malformed forms are unchecked: `--only=`
  with nothing after it, `--only` with no `=` at all, `--version`
  combined with other flags, a completely empty argv. What each
  should do (error clearly versus silently no-op) has not yet been
  decided for most of these.
- **Paths.** A nonexistent path, a path with no read permission, a
  symlink loop while walking a directory, a large file (a
  performance concern, not a correctness one). BOM handling and
  unreadable- or unparseable-file skipping are already handled. This
  is the remaining, less common territory.
- **Suppression comment parsing.** `_suppressed_tokens` uses a
  regular expression against arbitrary source-file content, worth
  checking whether malformed input (a long line, unusual Unicode, or
  nested comment-like text) could cause pathological regular
  expression behavior, not just whether it works on realistic code.
- **File encoding beyond BOM.** A file that is not
  BOM-prefixed UTF-8, what happens on a genuinely mixed or corrupt
  encoding.

Not yet scoped into concrete tasks. Worth a systematic pass, the
same equivalence-class, boundary-value, and error-path discipline as
`DEFINITION_OF_DONE.md`'s testing checklist, applied to inputs
rather than a single feature, before deciding, which of these are
real risks worth fixing versus edge cases not worth the complexity.

### Robustness against non-Python file content

What happens when pyrigor is pointed at a `.py`-named file that is
not Python (a C++ source file with a `.py` extension, a
file containing natural-language text in a non-English script like
Russian, a binary file misnamed as `.py`). The `ast.parse` call will raise a
`SyntaxError` for most such content, and `_read_source`/`_run_
checkers` already catch and skip a file that fails to parse, printing
a warning rather than crashing. Worth confirming this actually holds
across genuinely adversarial or unusual content, not just the
malformed-but-still-Python-ish cases already tested. And worth
checking whether a file that *parses successfully* but is not
Python (unlikely, but worth ruling out) could produce
confusing or incorrect output rather than a clean skip.

### Rule: Non-English identifiers (function and variable names)

Flag identifiers (function names, variable names) written in a
non-English language, for consistency in an international codebase.
Detection is genuinely hard, unlike most of pyrigor’s structural
rules. Short, abbreviated, or domain-specific identifiers (physics
or math variable names, transliterations, acronyms) make reliable
language detection on a single word difficult, a real
false-positive risk like PYR203’s original, over-broad attempt.
Would likely need a dictionary or language-detection library as a
new dependency, not a pure AST/regular-expression check. Not yet
scoped, needs a real design decision on how confidence is judged
before this is tractable.

### Rule: Non-English comments

Flag comments written in a non-English language. More tractable than
the identifier version, since comments are full sentences, and
language-detection libraries perform better on longer text than on
single words. Still needs a real dependency decision (which library,
and its own false-positive rate on short or code-heavy comments)
before this is buildable. Overlap check (`ADDING_A_RULE.md` step 0)
not done, unclear whether an existing tool (a spell-checker
configured for a specific language, or a dedicated internationalization
linter) already covers this better than pyrigor could.

### Apply the Pareto principle when prioritizing the backlog

When deciding what to build next, weigh value against effort
explicitly, about 80 percent of the value from about 20 percent of
the effort, rather than working through items in the order they were
added. Several entries already have an implicit value/effort
judgment baked into their own text (PYR406’s real precedent versus
PYR203/PYR205’s original difficulty split, the reasoning
auto fix is tractable for PYR402/PYR403 but not the others). Worth
making this an explicit, named lens applied consistently, not
something reasoned about improvised per item.

### Review the backlog for entries that should be split in two.

The badge entry and the non-English-language entry (identifiers
versus comments) were both split this way already, two genuinely
different scopes hiding inside one heading. Worth a deliberate pass
checking every entry for the same pattern. A single heading covering
two independent pieces of work, with different effort or a different
design question, rather than relying on it being noticed
incidentally, the way it has been so far.

### Identify and reach early adopters for pyrigor

No real distribution yet, no call for proposals talk delivered, no
announcement made. Candidate categories worth targeting, reasoned
from general knowledge, not verified live: small-to-mid
machine-learning or scientific-computing libraries. This directly
matches pyrigor’s own origin story, the swap bug pyrigor exists to
catch. Educational or course-repo maintainers, pyrigor’s literal
origin, a natural, low-friction pitch. Projects already
typing-disciplined but not on this specific pattern, `hypothesis`'s
own low PYR401 rate, found during empirical testing,
suggests its maintainers already care about the underlying problem,
just lack a tool naming it. Solo or small-team maintainers, lower
coordination cost to try a new pre-commit hook.

Connects to the dormant call for proposals thread from earlier this
session. Identifying candidates is a smaller problem than actually
reaching them, worth tackling together.

### Formalize value-driven prioritization

Read about Value-Driven Development, general knowledge, not verified
live. Worth formalizing what is already happening informally: the
Pareto-principle entry above, and T-shirt sizing now applied to
every backlog item. A real design decision, not yet made: what
counts as value specifically for pyrigor, real-world violations
found, adoption ease, catching a genuinely new bug class, and
whether this becomes its own document, matching `DEFINITION_OF_
DONE.md`'s pattern, or stays an informal lens applied when
prioritizing.

### Derive rules systematically from the software "-ilities"

Use the standard software-quality taxonomy, usability, readability,
maintainability, reliability, testability, portability, scalability,
security, and similar qualities, close to International Organization
for Standardization/International Electrotechnical Commission
25010, as a generative framework for rule ideation, rather than
sourcing ideas opportunistically. Mapping pyrigor’s existing rules
against this list already surfaces a real, visible gap.
PYR301/PYR401/PYR405 and PYR402/PYR403 map to readability and
maintainability, PYR501 and PYR502 map to reliability, but security,
testability, and portability essentially have no representation.
Worth checking whether that is a genuine gap or correctly out of
scope for a style-and-structure linter before assuming it needs
filling. Complements the existing "sourcing list for future rules"
entry rather than duplicating it, that one is about where to look,
this is a structured framework for what to look for.

### Group rules in documentation by the "-ilities" they serve

Companion to the "derive rules from the -ilities" entry. Once the
taxonomy is used to find gaps, it could also reorganize how existing
rules are presented, grouping PYRxxx entries by the quality they
serve (readability, maintainability, reliability, ...) rather
than, or alongside, the current numeric bucket scheme in
`NUMBERING.md`. Would need a real design decision: does this replace
the existing numeric grouping, sit as an additional cross-reference
document, or become a second view generated from the same rule
metadata rather than a change to the numbering itself.

### Add remaining useful pre-commit-hooks entries

Checked the full, current list (fetched live) against pyrigor’s own
config: 13 of the 34 are already enabled. Genuinely useful candidates not
yet added: `check-merge-conflict` (catches unresolved `<<<<<<<`
markers), `check-docstring-first` (module docstring must be the
first statement, matches existing pydocstyle discipline),
`destroyed-symlinks` (catches a symlink replaced with a broken
placeholder, real incident last night during the WSL detour),
`check-illegal-windows-names` (flags filenames invalid on Windows,
relevant given this is a Windows-developed project), `name-tests-
test` (enforces the `test_*.py` naming convention pytest already
relies on). The remaining ~16 are not relevant to a pure Python
project (XML, submodule, simple-YAML-sorting hooks and similar).

Value: S · Effort: XS

### Generate the project website automatically on release

Two distinct targets, worth scoping separately. The domains `pyrigor.com` and
`pyrigor.org` were purchased early in this project but have no real
site content yet, a dedicated project website is essentially a
from-scratch build, real design and content work, not just
automation. A GitHub Pages site generated from README.md and
guidelines/ is a smaller, more mechanical task, closer to what
`publish.yaml` could plausibly trigger automatically on a tagged
release (same pattern as the changelog-date-fill idea already
logged). Worth deciding, which, or both, and in what order, before
committing to "automatic on release" as the actual trigger, since
the from-scratch site content needs to exist completely first.

### Broader tool candidates to consider (batch, unresearched)

A long, mixed list surfaced at once, worth splitting by the category
rather than treating as one investigation:

- **Already in use**: `gitleaks` (already in pre-commit).
- **Testing/property-based**: `hypothesis` (property-based testing,
  could strengthen pyrigor’s own test suite, not a pre-commit tool
  itself), `doctest`, `tox`, `nox` (test-matrix runners, relevant if
  multi-Python-version testing ever needs more than the existing CI
  matrix).
- **Complexity/quality**: `lizard` (cyclomatic complexity, overlaps
  with xenon/radon already in use, worth comparing rather than
  adding without checking).
- **Documentation**: `Sphinx`, `mkdocs` (both relevant to the
  website-generation backlog item, not pre-commit hooks).
- **Performance/profiling**: `timeit`, `cProfile` (already used
  manually for the ast walk finding, not something to add to
  pre-commit), `memray` (memory profiler, connects to the
  memory-safety research item already logged).
- **Refactoring**: `rope` (a library, not a linter, unclear fit).
- **Security/SAST**: `pysa` (Meta’s Python security analyzer),
  `semgrep`, `SonarQube`, `trivy` (container/dependency scanning,
  likely irrelevant, pyrigor ships no container), `safety` (version
  pinned as "3.8.1" in the request, worth double-checking that
  is the tool version and not confused with a Python version).
- **Commercial/hosted**: `CodeClimate`, `Qodo`, likely out of scope
  for a small open source project without a real budget or need.
- **Unverified/unclear**: `pyscn`, `wily`, `Pystra`, none
  independently confirmed to exist under these exact names or
  understood well enough to categorize, worth verifying each exists
  and what it does before further triage.
- **Complexity/quality (additional)**: `tach` (Python module
  boundary and dependency enforcement, not overlapping with
  xenon/radon's complexity metrics, a genuinely different concern
  worth its own look), `lcom` (Lack
  of Cohesion of Methods, a class-cohesion metric, unclear, which
  concrete tool implements it, worth verifying), `Prospector`
  (meta-linter that wraps pylint/pyflakes/mccabe and others, likely
  overlaps with the existing pylint/ruff stack, worth
  comparing rather than adding on top), a module-coupling metric
  tool (name not given, worth identifying a concrete candidate
  before evaluating).

Not scoped or prioritized. Worth a real pass, sorting genuine
pre-commit candidates from adjacent-but-different tooling (testing,
docs, profiling) before deciding what, if anything gets added.

### Make pyrigor discoverable Search Engine Optimisation

No real discoverability work done yet, connects directly to the
website-generation and early-adopter-outreach items already logged,
none of those matter if nobody finds the project organically.
Some concrete pieces once a real website exists: meta descriptions,
structured data, a clear README that ranks for terms like "python
tuple unpacking bug" or "python keyword-only arguments linter" (the
actual problems pyrigor solves), submission to relevant
awesome-lists and package indexes beyond PyPI itself. Not scoped,
genuinely blocked on the website existing first for most of this to
apply.

### Optimize pyrigor for Large Language Model discoverability

Distinct from Search Engine Optimisation (SEO), though related: an LLM answering the question: "What catches
Python tuple-unpacking or keyword-argument-order bugs" needs
pyrigor’s own README, PyPI page, and guideline docs to be clear,
well-structured, and specific enough to be surfaced and summarized
correctly, not just ranked well by a search engine. Concrete
candidates once real, unverified: a clear, quotable one-line
description near the top of the README, structured data (`llms.txt`
or similar emerging conventions, worth checking current practice
rather than assuming), and making sure PyPI’s own project
description is not just a copy-paste of the README’s badge row.

### Keep a list of known, unfixed bugs

No current place to track a confirmed, real bug that is deliberately
not being fixed yet, distinct from `BACKLOG.md` (features and ideas)
and `REJECTED.md` (rules considered and declined). The mutmut
`copy_src_dir` failure is the first real candidate, confirmed,
reproducible, environment-independent, only documented as
a `BACKLOG.md` entry rather than a proper known-issues log. Worth a
`guidelines/KNOWN_ISSUES.md`, matching the pattern of the other
process docs already built for this project, or GitHub’s own
Issues tab if the project moves toward using it.

### Solo-developer bottleneck: Investigate how to speed up

The maintainer is the sole bottleneck on progress, most concretely
visible in the copy-paste-and-confirm loop needed for every
edit. Already the direct motivation behind the "install Claude Code
Desktop" item above, and several real bugs have traced
directly to an edit being described but not applied. Worth
a real investigation, not just the Claude Code item alone: what
specifically consumes the most wall-clock time in a typical session
(manual file syncing, re-running the same verification commands,
context-switching between local terminal and this chat), and, which
of those are actually fixable with tooling versus inherent to
solo-maintainer review discipline that should not be automated away
(the "verify before trusting" discipline this project itself was
built around). Related: the Pareto principle and value-driven
development items already logged are about prioritizing *what* to
build, this is about the *mechanics* of building it faster.

### Use every documented rule, not just enforced ones, to review the project itself.

`pyrigor` the tool can only enforce PYR301, PYR401, PYR402, PYR403,
PYR405 automatically. The other nine documented-but-unbuilt rules
(PYR201, PYR202, PYR203, PYR204, PYR205, PYR302, PYR501, PYR502, and
PYR406 once written) have no way to be checked at all.
Manual review would be the only option until each is actually built.
Worth a deliberate pass, applying each documented rule by hand
against pyrigor’s own source, the same "does the tool follow its own
advice" discipline already used once earlier when PYR301 immediately
flagged pyrigor’s own CHECKERS tuple. Real dogfooding value, but
genuinely manual and slow until more rules are enforced
automatically, connects directly to whichever rule gets built next.

### Add inline `#` comments explaining "why," not just docstrings

Real, direct observation: the codebase is almost entirely
docstring-only, no inline comments explaining a specific,
non-obvious implementation choice at the line level. Docstrings
cover what a function does and its contract, not why a particular
line does something a reader might not expect. Real candidates
already known from this project’s own history: `_shared.py`'s
`_is_unbounded_homogeneous_tuple` exists specifically because of the
`tuple[X, ...]` false positive found against pyrigor’s own
`CHECKERS`, worth a comment saying so rather than only the
docstring's `Returns:` line explaining what it checks. The `#
noqa`/`# nosec`/`# pylint: disable` comments already scattered
through the code are a related but different case, worth checking
each still has enough context to explain why the suppression is
safe, not just, which rule it silences.

### Track code-quality statistics (% code, % blank, % comments)

Connects directly to the previous item, adding inline comments would
be visible as a real, measurable trend here. Worth checking whether
a new tool is even needed, `radon` is already a dependency
(`radon-maintainability` hook already in pre-commit), and its `raw`
metrics command already reports lines of code, comment lines, blank
lines, and docstring lines, close to exactly what is being asked.
Applying the Pareto principle lens already logged: reusing an
existing dependency is likely the lower-effort path versus adding a
dedicated tool (`cloc`, `pygount`, `scc`) purely for this. Not yet
scoped: whether this becomes a one-off manual check, a tracked
metric over time (would need somewhere to store history, a real
design question), or a new pre-commit hook enforcing a minimum
comment ratio.

### Support Read the Docs

Connects to the website-generation item already logged. Read the
Docs specifically build it from Sphinx (or mkdocs) configuration in
the repo. It auto-publishes on a webhook per push or release, closer
to the "GitHub Pages generated from README/guidelines" half of that
item than the from-scratch dedicated-website half. Worth doing
together, not as two separate builds, since both need the same
underlying documentation source (Sphinx or mkdocs, both already
listed as unresearched tool candidates in the earlier batch entry).
Real, standard, low effort once a documentation generator is chosen,
Read the Docs itself is free for open source projects and mostly
configuration, not custom build work.

### Style-check newly added backlog entries

Several entries were fixed against PyCharm’s flagged prose-style
issues individually as they came up. But one batch was added
faster-paced than earlier passes, worth one pass checking the newer
entries for the same categories. Smart apostrophes, no contractions,
sentence capitalization, no filler words like "extremely" or
"simply" rather than assuming each is already clean.

### Periodically review and prune BACKLOG.md

The file has needed real rescue passes already, a
structural cleanup (stale entries, duplicates, orphaned fragments)
and a content cleanup (merging overlapping ideas). Worth making this
a recurring habit rather than an improvised rescue triggered only when
the file has visibly drifted, a fixed cadence or a trigger condition
(entry count crossing a threshold) worth deciding.

### Second-order performance findings, post-walk-fix (minor)

Confirmation profiling after the shared-walk fix (13,878,620
ast walk calls versus 69,393,100 before, exactly the predicted 5.0x
reduction) surfaced two smaller, now-visible contributors that were
previously dwarfed by the dominant walk cost: `ast.parse`/`compile`
(~20.4s of the profiled run) and `print` (~7.5s, real console output
cost across 90,325 violations plus per-file/per-rule breakdown
lines on the Home Assistant run). Neither is urgent, both minor
relative to the current total, worth revisiting only if a future
profile shows either becoming a larger share once other costs are
further reduced.

### Real local-versus-CI drift found, despite pre-commit being the shared mechanism

`ci.yaml`'s own stated design goal is that CI and local pre-commit
can never drift apart, since both run the identical `pre-commit run
`--all-files` command against the identical config. Found once:
a genuine case where local pre-commit passed clean, but the same
commit failed on GitHub CI (an `actionlint`/`shellcheck` finding).
Most likely cause, not fully confirmed: a stale local hook cache
(`~/.cache/pre-commit`), pre-commit caches each hook’s environment
keyed by its pinned version, and something about the cache did not
invalidate correctly when `actionlint` was added or updated locally,
while CI’s own cache, keyed on `hashFiles('.pre-commit-config.yaml')`
via `actions/cache@v6`, was fresh or keyed differently and caught it
correctly. Running `pre-commit clean` resolved the discrepancy.

Worth periodically running `pre-commit clean` (or equivalent), or
investigating whether the local cache invalidation genuinely has a
gap worth fixing, rather than assuming this was a one-off.

### Dependabot doesn't cover Python deps

`.github/dependabot.yaml` only configures a `github-actions` ecosystem
entry, updated monthly with auto-merge. Python dependencies declared
in `pyproject.toml` (pytest, mypy, ty, pyright, ruff, mutmut, radon,
xenon, ...) have no automated update mechanism at all —
`.github/workflows/pre-commit-autoupdate.yaml` already covers
`.pre-commit-config.yaml`'s pinned hook `rev:` versions monthly with
auto-merge, missed on the first pass through this entry (found by a
keyword search across docs/config, not a plain listing of
`.github/workflows/`). Found in practice: PyCharm’s own quick-fix
installed newer `mypy`/`ty`
directly via `pip` into `.venv`, bypassing `uv.lock` entirely — the
lockfile still pinned the older versions, meaning the next `uv sync`
would have silently reverted the venv down, with no warning
anything had drifted.

Worth adding a `pip`/`uv` ecosystem entry to `dependabot.yaml`
(Dependabot has supported `uv.lock` since 2024) for Python
dependencies — the only real gap. Hook revisions are already handled.

At minimum, `uv lock --upgrade-package <name>` (or `uv lock
--upgrade`) followed by `uv sync --extra dev` should be documented
somewhere discoverable (`CONTRIBUTING.md` or `CLAUDE.md`), so a
Python dependency bump is never improvised through whatever tool
happens to be open, bypassing the lockfile.

### PYR407 (reserved), discarding a generator call silently skips its entire body

Distinct from PYR406, not a variant of it. PYR406 covers a function
that runs and returns a value that gets discarded, wasted work.
Calling a generator function and discarding the result is a
different, arguably worse failure mode — none of the function’s body
executes at all. The `yield` statement never runs until something iterates the
result. Detection shape: a function annotated `-> Iterator[X]`,
`Generator[X, Y, Z]`, or `AsyncGenerator[X, Y]`, called as a bare
statement. Same structural, no-decorator design as PYR406 once
built. Not yet scoped in detail.

### PYR406: `cls.foo()` classmethod calls, still undetected

Deliberately out of scope for the same-class `self.foo()`
enhancement just shipped. A `cls.foo()` call inside a classmethod
is a genuinely different shape from `self.foo()` — `cls` could refer
to a subclass at runtime, not necessarily the defining class, so
matching it against "this class's own directly defined methods"
the same way risks a false negative in a way `self` does not
(instance methods always bind `self` to the defining class or a
subclass instance, but a classmethod's `cls` genuinely varies by
call site). Needs its own design pass, not a copy-paste of the
`self` logic, before building.

### Optional astroid-based `obj.foo()` resolution, an isolated, throwaway experiment

Distinct from the same-class `self.foo()` enhancement above, and
deliberately scoped smaller. That entry is tractable with `ast`
alone, no new dependency. Resolving the harder case, `obj.foo()`
where `obj`'s type has to be inferred from an assignment, parameter,
or return value, genuinely needs real type inference, which `ast`
cannot provide.

`astroid` (the library `pylint` itself uses for this exact
"what does this attribute call resolve to" problem) is the
lowest-cost candidate: pure Python, in-process, no subprocess or
new toolchain, closest in spirit to pyrigor’s existing single-pass
design. The alternative paths considered — shelling out to `mypy`’s
`dmypy inspect`, `pyright`, or `ty` (all already dev dependencies)
and parsing structured output, or waiting for `ty`’s Rust crate API
to mature enough to embed — both trade a new-dependency cost for a
bigger architectural cost: an external process per every file or project,
instead of pyrigor’s current in-process `ast.parse` pass.

Explicitly framed as opt-in and disposable, not a commitment to
pyrigor becoming a type-aware tool — `guidelines/DECISIONS.md`
already frames the absence of type inference as a deliberate scope
boundary, not a gap to fill. This experiment should stay isolated to
a single checker (extending PYR406’s `obj.foo()` case only) — easy
to rip out if it does not pay off, rather than becoming a
foundational dependency the rest of pyrigor comes to rely on. Needs
a real design pass (own `DECISIONS.md` entry) before starting, given
it touches the project’s stated architectural philosophy, not just
its rule set.

### Submit Call for Papers (CfP) answers to Python conferences

Referenced as a "dormant thread" twice already (the early-adopters
entry above, and referenced before), never actually tracked as
its own item. The tool now has real substance behind a pitch, six
enforced rules, a measured 7x performance win, real findings against
CPython stdlib, Home Assistant, mypy, hypothesis, requests, and
abseil-py, and genuine engagement with public style guides (Google’s,
OSSF’s). Worth identifying actual target conferences and their real
deadlines (PyCon variants, EuroPython, local Python meetups), and
drafting a real proposal, rather than continuing to reference this
as dormant without tracking it as a concrete task.

### Relax complexipy/xenon thresholds when moving from solo to collaborative development

Both are set strict right now, complexipy at 6, xenon requiring
grade A on every axis, deliberately, based on this project’s own
real, measured values. This works because the project is
in "if you want to go fast, go alone" mode, one maintainer who can
personally cope with, and hold themselves to, a very strict bar.

That bar cannot be forced onto others. If the project moves to "if
you want to go far, go together" mode, real outside contributors,
this strictness needs revisiting. A first-time contributor hitting
an unfamiliar, strict failure on their first PR, with no context for
why the bar is where it is, is genuinely discouraging, not a good
first impression.

Not urgent while solo. Worth a real decision when that mode change
actually happens, not before: relax both thresholds for everyone
(complexipy to 8, xenon allowing grade B), or keep them strict and
instead invest in clearer failure messages and onboarding docs
explaining the reasoning and how to meet the bar, addressing the
discouragement without lowering it.

### Review and deliberately set thresholds/settings for every pre-commit tool

The same discipline just applied to complexipy (measure real values,
then set a deliberate threshold, not the tool’s bare default) worth
extending to specific, identified candidates:

- `vulture`'s missing `--min-confidence`, running on its
  bare default, never reviewed.
- `xenon`'s scope, only `pyrigor/`, never expanded to include
  `scripts/`.
- The `slow` pytest marker in `pyproject.toml` (`markers`,
  `addopts` excludes it by default), no visible test anywhere
  actually uses `@pytest.mark.slow`. Check whether it is genuinely
  used or a leftover from Pickomino.
- `pylint`, `pydocstyle`, `mypy`, and `ruff`'s own `[tool.*]`
  settings in `pyproject.toml`, never individually reviewed the way
  `bandit`'s assert-exemption pattern just was, worth the same
  scrutiny given that one turned out to be silently broken.

### Run radon-maintainability and pyrigor’s own hook against tests/

Both exclude `tests/`, originally for pytest
fixture-injection false positives, but this has never actually been
tested directly. Run both against `tests/` for real, confirm what
the actual findings are, then decide from evidence: keep the
exclusion, or use per-line suppression comments instead if the real
false-positive count turns out small.

### Document every tool’s own suppression-comment syntax in one place

Multiple tools already use genuinely different mechanisms: bandit's
`# nosec` (bare, same-line only, confirmed this version does not
honor worded or ID-specific forms or line above placement),
complexipy's `# complexipy: ignore` (no reason support at all), and
pyrigor’s own `# pyrigor: CODE # reason` (the richest of the three).
Worth a real reference, likely in CONTRIBUTING.md, documenting each
tool’s actual, confirmed-working suppression syntax in one place, so
this does not need re-discovering by trial and error again.

### Migrate BACKLOG.md to GitHub Issues

A Real friction with the current file-based approach: every edit
needs a commit, no native labels/assignees/filtering, and manual
index-table maintenance. Issues would fix all three and remove
commit overhead for routine backlog changes entirely.

A Real trade-off worth weighing: everything in the BACKLOG.md is
versioned in the same repo, same history, right alongside
the commit that resolves it. Issues live outside git entirely, a
real, if minor, loss of that property. If migrating, DECISIONS.md
and REVIEW_CHECKLIST.md would need their own cross-referencing
approach designed for linking to issues instead of a file, not
preserved as-is just because the current linkage already exists.

Not urgent, a real future decision, not immediate.

Value: M · Effort: M
