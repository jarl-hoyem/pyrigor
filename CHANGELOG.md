# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project is in the `0.x` series, so minor version bumps do not
carry the same backward-compatibility guarantee they would after
`1.0.0`. Patch bumps are the default for incremental changes. Minor
bumps are reserved for changes that shift what pyrigor
is usable for.

## [Unreleased]

### Changed

- CLI argument parsing (`--version`/`-V`, `--select`, paths) now uses
  the standard library's `argparse` instead of hand-rolled `sys.argv`
  scanning (#51). Real behavior improvements: `--select PYR401`
  (space-separated) now works, previously only `--select=PYR401` was
  recognized. An unrecognized flag is now an error immediately instead of
  being silently treated as a path. Also `--help` is now available.
- `--only` renamed to `--select`, matching ruff's naming convention
  (#68). Same behavior, no deprecated alias — pyrigor has no users
  yet.

### Added

- `--ignore=CODE,CODE` flag, the rule-axis opposite of `--select`
  (#69). Excludes specific rules while running every other one;
  combines with `--select` (start from its set, remove `--ignore`'s
  codes) the same way ruff's own `select`/`ignore` combine. A
  combination that leaves no rules to check errors immediately.

## [0.8.0] 2026-08-20

### Fixed

- `pyrigor`'s CLI output hardcoded "Function" for every violation,
  even ones that are not functions — a PYR301 violation on an
  annotated variable printed `Function 'x' ...` instead of
  `Variable 'x' ...`. `Violation` now carries a `context_kind`,
  set correctly per node type (Function/Variable/Call). Closes #11.

### Changed

- Suppression comments drop the colon after "pyrigor": `# pyrigor:
  CODE # reason` → `# pyrigor CODE # reason`. The colon form collided
  with ruff’s ERA001 (commented-out-code) when a suppression comment
  sat on its own line, since `pyrigor: 402` parses as valid Python (a
  bare annotation) and ERA001 flags any standalone comment that
  parses. This is a permanent syntax change, not a temporary
  workaround — existing colon-based comments will stop suppressing
  (they now print a near-miss warning instead of silently doing
  nothing, so the break is visible, not silent). Closes #46.

## [0.7.4] 2026-08-19

### Fixed

- `pyrigor` double-counted files and violations when the same file
  was reachable through two different path arguments (an overlapping
  directory argument, a relative versus absolute form) — for example
  `pyrigor $(git diff --name-only) .` in a CI script. `_collect_python_files()`
  now deduplicates by each file’s resolved path while keeping its
  first-seen string form for output. Closes #8.
- `--only=` given a second time was silently treated as a path
  instead of erroring — `pyrigor --only=PYR401 --only=PYR402 file.py`
  dropped the second rule code entirely and produced a confusing
  "no such file" warning. A repeated `--only=` flag now errors
  immediately (exit code 2) instead. Closes #10.
- Suppression comments were matched against each candidate line’s
  raw text via the regular expression, with no awareness of Python’s lexical
  structure. A string or docstring literal whose contents happened
  to exactly match `# pyrigor: CODE # reason` syntax could silently
  suppress a real violation on that line, since regular expression over raw text
  cannot distinguish a genuine comment from text that merely looks
  like one inside a string. Suppression matching now tokenizes the
  source and only considers genuine comment tokens. Closes #41.

## [0.7.3] 2026-08-18

### Added

- Suppression comments (`# pyrigor: CODE # reason`) may now also go
  on the line directly above a violation, or anywhere within a
  multi-line statement’s own span, not just the violation’s exact
  starting line. Closes #31.

## [0.7.2] 2026-08-18

### Added

- PYR406 now also detects a discarded `self.<name>()` call, when
  `<name>` is defined directly on the same class as the calling
  method — previously any `self`/`cls`-taking function was excluded
  from detection entirely. Still out of scope: a subclass calling an
  inherited method through `self`, a `cls.<name>()` call, and any
  attribute call through something other than `self`
  (`obj.compute_total()`) — none of these are resolvable without
  real type inference, which pyrigor deliberately does not do.

## [0.7.1] 2026-08-18

### Fixed

- PYR406 silently missed a PEP 604 union return type (`int | str`,
  `int | None`). `_annotation_name()` did not recognize the `X | Y`
  syntax, treating it the same as an unrecognized annotation shape
  — indistinguishable from `-> None` to the checker, so the
  function’s discarded return value was never flagged. Now
  detected and protected like any other non-`None` return type.

## [0.7.0] 2026-08-17

### Added

- PYR406 (return values used) is now enforced, a sixth rule. Flags a
  bare-statement call to a locally defined, non-`None`-returning
  function whose result is discarded. Scoped to bare-name calls only
  — a call through attribute access (`self.foo()`, `obj.foo()`) is
  out of scope, since pyrigor cannot reliably determine which class
  or object it belongs to from the AST alone. Functions with a
  leading `self`/`cls` parameter are therefore excluded from the
  protected set entirely, to avoid a method’s name leaking a false
  positive onto an unrelated bare call sharing the name.

## [0.6.0] 2026-08-16

### Added

- Per-rule suppressed-violation counts in the summary (`PYR402: 1
  suppressed`), alongside the existing per-rule and per-file
  violation breakdowns.
- `PYR502`'s guideline doc corrected: recommends `raise` instead of
  `assert` for correctness checks, since Python's `-O` flag strips
  every `assert` from compiled bytecode entirely.
- `--only=CODE,CODE` CLI flag to restrict checking to specific
  rules. Accepts full code, bare number, or symbolic name.
- `scripts/check_dod.py`, a warn-only pre-commit hook. Prints a note
  (never fails the commit) if the `pyproject.toml`'s version changed
  without a matching `CHANGELOG.md` entry, or if
  `pyrigor/checkers/`/`rules.py` changed without a `README.md`
  change, pointing at `guidelines/DEFINITION_OF_DONE.md`.

### Changed

- `filter_suppressed` now returns `SuppressionResult(kept,
  suppressed)` instead of a bare list, so suppressed violations can
  be counted and reported rather than silently discarded.
- `CHECKERS` restructured to explicit `RegisteredChecker(rule,
  find_violations)` pairs, removing an implicit, unenforced assumption
  that `CHECKERS` and `Rule` shared the same declaration order.
- Every checker now shares a single `ast.walk()` per file instead of
  walking independently. Confirmed via profiling: `ast.walk`'s own
  call count dropped 5.0x (69,393,100 to 13,878,620 on an 18,187-file
  run), real-world timing on the same run dropped from 388.20 s to
  55.46 s, 7x.

### Fixed

- Per-rule breakdown and per-file breakdown print order: both were
  still printing before the per-file list on a second pass, only the
  total line had actually been fixed the first time.
- `--only` with an unrecognized rule code now errors immediately
  (exit code 2) instead of silently running zero checkers.

## [0.5.0] 2026-08-14

### Added

- PYR301 (NamedTuple values) is now enforced, a fifth rule. Covers
  a bare multi-value tuple annotation on a plain variable, dataclass
  field, or attribute assignment, complementing PYR401 (returns) and
  PYR405 (parameters).
- Per-file violation breakdown in the summary, alongside the
  existing per-rule breakdown.

### Changed

- `Violation.function_name` renamed to `context_name`, and
  `make_violation` generalized to accept `ast.AnnAssign` nodes
  alongside function nodes, since PYR301 is not a function-shaped
  rule.
- `find_violations_by_predicate` split into
  `find_function_violations` and `find_assign_violations`, one
  dispatcher per node shape, rather than one generic dispatcher over
  a three-way union (a single generic version hit real `Protocol`
  contravariance problems).
- `is_bare_multi_value_tuple` now exempts `tuple[X, ...]`, the
  unbounded homogeneous form, found via pyrigor’s own `CHECKERS`
  tuple immediately triggering a false positive once PYR301 went
  live against its own source.
- PYR203 rewritten to a strict, mechanical rule (any number other
  than `0`, `1`, or `-1` must be a `Final` constant), following
  Steve McConnell’s actual *Code Complete* formulation, replacing an
  earlier, softer "self-explanatory" exemption that reintroduced the
  exact judgment call the rule was meant to eliminate.

### Fixed

- `BACKLOG.md`'s item #5 removed a stray "this session" reference,
  meaningless outside a live coding session.
- Summary print order: per-file breakdown, per-rule breakdown, and
  the total line now print in that order, all three surviving
  scrolling off the screen on a large run. Found in two passes against
  Home Assistant core (18,187 files): the first fix only moved the
  total line, the per-rule breakdown was still printing before the
  per-file list and scrolling off the same way.

## [0.4.0] 2026-08-13

### Added

- PYR403 (keyword-only single argument) is now enforced, a fourth
  rule.

### Changed

- `count_parameters` and `find_violations_by_predicate` extracted
  into `pyrigor/checkers/_shared.py`, removing duplicated logic
  across all four checkers. Two new `Protocol` types
  (`_PredicateFun`, `_CheckerFun`) added, since a bare `Callable`
  type hint cannot express a keyword-only calling convention.
- Every checker’s own `_has_violation` and `find_violations`, plus
  `cli.py`'s `main`, are now keyword-only themselves, fixing nine
  real PYR403 violations pyrigor found in its own source the moment
  the rule went live.
- `.pre-commit-config.yaml`'s `pyrigor` hook now uses
  `pass_filenames: false` and always checks the whole `pyrigor/`
  directory, matching every other whole-project tool already
  configured that way, instead of receiving batched, per-commit
  filenames from pre-commit’s default behavior.

### Fixed

- The summary line’s em dash was displayed as a garbled non-printable
  character in PowerShell. Replaced with a plain ASCII double hyphen.

## [0.3.0] 2026-08-13

### Added

- PYR405 (NamedTuple parameters) is now enforced, a third rule.
- `--version` flag on the `pyrigor` CLI.
- Per-rule violation count breakdown in the summary line.
- CI: a standard library smoke test on every commit, and a Home Assistant core
  smoke test before every release, gating the "publish" script if pyrigor
  crashes against it.
- `PERFORMANCE.md`, `guidelines/PYR203-final-not-magic-numbers.md`,
  `guidelines/NUMBERING.md`, `guidelines/ADDING_A_RULE.md`,
  `guidelines/REJECTED.md`.

### Changed

- Every checker now runs against a single shared `ast.parse()` per
  file instead of each parsing independently.

### Fixed

- `main()` returned exit code 1 for both "violations found" and any
  genuine crash, so nothing could reliably distinguish the two.
  `run()` now catches unexpected exceptions and exits with code 2,
  reserving 1 for "ran fine, found violations." Found via the new
  stdlib CI smoke test, which was failing on real violations rather
  than an actual crash.
- The CI smoke test steps' `if [ $? -eq 2 ]` check never actually
  ran: GitHub Actions fails a `run:` step immediately on any
  non-zero exit code by default, so the step already failed on
  pyrigor’s own exit code 1 (violations found) before the shell ever
  reached the check. Both `ci.yml` and `publish.yaml`'s smoke test
  steps now use `set +e` around the pyrigor call, capture `$?`
  immediately into a variable, then re-enable `set -e` before
  checking it.

## [0.2.3] 2026-08-13

### Fixed

- `site-packages` directories are now excluded by default during
  directory walks, regardless of the containing venv folder’s own
  name.
- A single unreadable or unparsable file no longer crashes the run.
  Files that cannot be decoded or contain invalid syntax
  are skipped with a warning and do not affect the exit code.

## [0.2.2] 2026-08-13

### Fixed

- Source files with a UTF-8 byte order mark (BOM) crashed pyrigor
  entirely instead of being checked normally. `_check_file` now
  reads with `encoding="utf-8-sig"`.

## [0.2.1] 2026-08-13

### Added

- `pyrigor <path>` now accepts a mix of files and directories.
  Directories are walked recursively for `.py` files.
- Common vendored/generated directories are skipped automatically
  during the walk (`.venv`, `venv`, `.git`, `__pycache__`,
  `node_modules`, `.tox`, `build`, `dist`, `.eggs`, `*.egg-info`).
- Every run ends with a timing summary line.

## [0.2.0] 2026-08-13

### Added

- PYR401 (NamedTuple returns) is now enforced. Previously documented
  and implemented in isolation but not wired into the CLI or
  pre-commit hook.
- A `CHECKERS` registry replaces individual named re-exports, so
  adding a checker means one import and one tuple entry, not
  separate edits across multiple files.

## [0.1.1] 2026-08-12

### Fixed

- The v0.1.0 GitHub release was published before `publish.yaml`
  existed, so it never actually reached PyPI. This release fixes the
  publishing pipeline.
- PYR402’s guideline doc "Enforced by" section, which was stale.

## [0.1.0] 2026-08-12

### Added

- Initial PyPI release.
- PYR402 (keyword-only arguments, 2+ parameters): fully implemented,
  AST-based checker, `pyrigor` CLI, pre-commit hook.
- PYR201, PYR401, PYR403 documented, not yet enforced.
- Suppression mechanism: inline `# pyrigor: CODE # reason` comments,
  with lenient parsing (full code, bare number, or symbolic name. Comma-separated
  multiple codes), a mandatory reason, and a warning
  on malformed or near-miss suppression comments.
