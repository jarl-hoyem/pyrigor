# Performance

Real-world timing data from running `pyrigor` against codebases of increasing size, gathered while validating pyrigor's
suitability for large-scale use. Runs use a local source on Windows with Python 3.14. The historical measurements used
`uv run`; the migration measurements below use the worktree's own interpreter and the same CLI checking pipeline.

The historical Results table predates PYR301, PYR403 and the shared-AST-walk refactor. The Shared AST walk section
measures five checkers. The canonical finding migration measures the current six checkers, including PYR406. These
tables describe different rule sets, so their timings cannot be compared directly.

## Canonical finding migration

The pre-migration baseline is commit `032c900cc9bda7b43ce24012034ecaae786d20c3`, using pyrigor 0.13.1. Sources were
frozen with `git show` before any checker changes. The portable characterisation archive separately preserves the 36
committed Python files under `pyrigor/`, `tests/checkers/` and `manual-tests/`. It records 70 raw detections, of which
10 are kept and 60 suppressed, by file, rule and starting line.

Timing runs use Python 3.14.3 on Windows 11 (build 26200). Both corpora use every registered rule and default directory
exclusions. Each run uses CLI file collection and `_check_file`, without rendering findings or JSON. Timing starts after
collecting, matching the CLI's checking timer. These are single wall-clock observations on a shared machine, without
controlled filesystem cache or system load. Treat their differences as rough indications.

| Codebase            | Files  | Kept findings | Before  | After    |
| ------------------- | ------ | ------------- | ------- | -------- |
| CPython stdlib      | 1,844  | 21,209        | 60.913s | 33.233s  |
| Home Assistant core | 18,187 | 90,488        | 83.826s | 104.597s |

The CPython corpus is Python 3.14.3's standard library, excluding `site-packages`. It has three expected non-UTF-8 read
failures and one expected parse failure. Home Assistant is the core repository at
`80fd0c5fbbe147412c65f55b75f13c1e0ea22f35`, version 2026.9.0.dev0, with no operational failures. Neither corpus contains
suppressed findings. Per-rule baseline counts are:

| Codebase            | PYR301 | PYR401 | PYR402 | PYR403 | PYR405 | PYR406 |
| ------------------- | ------ | ------ | ------ | ------ | ------ | ------ |
| CPython stdlib      | 6      | 39     | 8,591  | 12,560 | 4      | 9      |
| Home Assistant core | 55     | 579    | 58,485 | 30,786 | 420    | 163    |

To repeat the comparison, check out the baseline and candidate revisions in separate directories outside the corpora.
Run each checkout in a separate process with its own import path, using the same Python version and corpus revisions.
Collect Python files with the CLI's file collection and default exclusions. Start a wall-clock timer after a collection,
then call `_check_file` for each file with every registered checker. Stop the timer after the final file, without
rendering the results. Total the kept and suppressed findings, operational failures and per-rule counts for comparison.

Before and after runs were sequential under the same execution context. Finding counts, suppression counts and
operational failures match on both corpora. The standard-library run became faster while the Home Assistant run became
slower. Cache and system load were not controlled, so these observations do not establish a general speedup or isolate
the cost of the migration.

## Results

| Codebase                | Files  | Violations | Time           | Files/sec |
| ----------------------- | ------ | ---------- | -------------- | --------- |
| ML course repo          | 29     | 76         | 0.17s          | ~170      |
| CPython stdlib (`Lib/`) | 1,844  | 8,634      | 15.89s–20.49s* | ~90–115   |
| Home Assistant core     | 18,187 | 59,086     | 90.21s         | ~202      |

\* Two runs in the same environment showed meaningful variance (15.89 s to 20.49 s). The likely cause is OS-level
file-system caching between runs, not a real change in pyrigor's own behaviour. Treat these timings as rough
indications, not precise benchmarks.

## Per-rule breakdown

Both large-codebase runs show the same lopsided pattern:

- CPython stdlib: PYR401: 43, PYR402: 8,591
- Home Assistant core: PYR401: 601, PYR402: 58,485

PYR402 (keyword-only arguments) outnumbers PYR401 (NamedTuple returns) by a factor of roughly 100 to 200 in both
codebases. Two unrelated projects showing the same lopsided ratio suggest it reflects how people typically write Python,
not an artefact of either codebase. Most functions take several parameters, and few return multi-value tuples.

## Shared AST walk (current)

Checkers previously each called `ast.walk()` independently, once per checker per every file, a real, avoidable cost that
scaled linearly with checker count, confirmed directly by profiling (`python -m cProfile`) against Home Assistant core:
`ast.walk` itself accounted for 286 of 388 seconds, the dominant cost.

Fixed by walking the tree exactly once per file (`walk_once()`), distributing the same collected nodes to every checker,
rather than each checker re-walking the tree from scratch.

| Codebase            | Files  | Violations | Time before | Time after | Speedup |
| ------------------- | ------ | ---------- | ----------- | ---------- | ------- |
| Home Assistant core | 18,187 | 90,325     | 388.20s     | 55.46s     | ~7x     |

Violation counts identical before and after (PYR301: 55, PYR401: 579, PYR402: 58,485, PYR403: 30,786, PYR405: 420),
confirming the refactor changed only performance, not correctness. The speedup exceeds the ~5x predicted from the
profiling data (five checkers reduced to one shared walk), likely because the earlier estimate did not fully account for
the internal cost of `iter_child_nodes` and `iter_fields`, both called proportionally to walk count.

This confirms the "Checker-count scaling" prediction below. The benefit compounds with each new checker, since each one
now costs only its own predicate evaluation over already-collected nodes, not another full tree walk.

## Findings

- **Home Assistant (larger, more files) ran faster per-file than the CPython stdlib** (~202 files/sec versus ~90–115
  files/sec) — evidence that pyrigor's cost scales with actual code complexity per file, not file count alone. The
  stdlib includes some huge, complex modules (`typing.py`, `re/_parser.py`). Home Assistant's codebase is many smaller,
  more uniform integration files.
- **No crashes across either large run**, including real edge cases the smaller ML-repo test did not surface: a UTF-8
  Byte Order Mark (BOM) crash, an unrelated non-UTF-8 file crash, and scanning into a differently named venv folder —
  all found and fixed before these runs (see CHANGELOG/release notes for v0.2.2 – v0.2.3).
- **Checker-count scaling**: architecturally, checkers previously each called `ast.parse()` independently — a real,
  avoidable cost that would scale linearly with checker count. Fixed by sharing a single parse per file across all
  registered checkers (see commit history). A controlled before/after comparison on this specific change showed ~15%
  improvement on the stdlib run with only two checkers. The larger, compounding benefit should grow with each new
  checker, since each one now costs only its own tree walk rather than another full parse.

## Not yet tested

- Parallelism/multiprocessing — deliberately not pursued. An estimate suggested a ~4x speedup ceiling (bound by CPU core
  count, since checking is CPU bound and Python's Global Interpreter Lock (GIL) prevents threading from helping). Judged
  not worth the complexity given current scale, and the diminishing-cost trajectory as checkers share a single parse.
  Revisit if real usage patterns show this actually matters.
- A Rust rewrite of the checker core (the ruff approach) — explicitly out of scope. Would be pursued for learning
  purposes rather than a demonstrated performance need, and is a fundamentally larger undertaking than anything else on
  this list.
