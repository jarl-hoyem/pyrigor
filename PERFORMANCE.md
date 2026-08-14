# Performance

Real-world timing data from running `pyrigor` against codebases of
increasing size, gathered while validating pyrigor’s suitability for
large-scale use. All runs used pyrigor’s local, unreleased source
(via `uv run` from within the pyrigor project itself), on a Windows
machine, Python 3.14.

All measurements below predate PYR301 and PYR403 (both added after
this document was first written) and reflect two, three, or four
enforced checkers depending on the run, not the current five. Kept
as historical data rather than re-run, since the qualitative
findings, per-file cost scales with code complexity, not file count,
no crashes on either large codebase, remain the relevant takeaways
regardless of exact checker count.

## Results

| Codebase                | Files  | Violations | Time           | Files/sec |
|-------------------------|--------|------------|----------------|-----------|
| ML course repo          | 29     | 76         | 0.17s          | ~170      |
| CPython stdlib (`Lib/`) | 1,844  | 8,634      | 15.89s–20.49s* | ~90–115   |
| Home Assistant core     | 18,187 | 59,086     | 90.21s         | ~202      |

\* Two runs, same environment, showed meaningful variance
(15.89 s – 20.49 s) — attributed to OS-level file-system caching between
runs, not a real change in pyrigor’s own behavior. Timing numbers
here should be read as rough orders of magnitude, not precise
benchmarks.

## Per-rule breakdown

Both large-codebase runs show the same lopsided pattern:

- CPython stdlib: PYR401: 43, PYR402: 8,591
- Home Assistant core: PYR401: 601, PYR402: 58,485

PYR402 (keyword-only arguments) dominates by two orders of
magnitude over PYR401 (NamedTuple returns) in both real, unrelated
codebases — consistent enough across two very different projects to
suggest this ratio reflects something structural about how Python
code is typically written (most functions take multiple parameters.
Few functions return multi-value tuples), not an artifact of either codebase.

## Findings

- **Home Assistant (larger, more files) ran faster per-file than the
  CPython stdlib** (~202 files/sec versus ~90–115 files/sec) — evidence
  that pyrigor’s cost scales with actual code complexity per the file,
  not file count alone. The stdlib includes some huge, complex
  modules (`typing.py`, `re/_parser.py`). Home Assistant’s codebase
  is many smaller, more uniform integration files.
    - **No crashes across either large run**, including real edge cases
      the smaller ML-repo test did not surface: a UTF-8 Byte Order Mark, (BOM)
      crash, an unrelated non-UTF-8 file
      crash, and scanning into a differently
      named venv folder — all found and fixed before these runs (see
      CHANGELOG/release notes for v0.2.2 – v0.2.3).
- **Checker-count scaling**: architecturally, checkers previously
  each called `ast.parse()` independently — a real, avoidable cost
  that would scale linearly with checker count. Fixed by
  sharing a single parse per the file across all registered checkers
  (see commit history). A controlled before/after comparison on this
  specific change showed ~15% improvement on the stdlib run with
  only two checkers. The larger, compounding benefit is expected as
  more checkers are added, since each additional one now only costs
  its own tree-walk rather than another full parse.

## Not yet tested

- Parallelism/multiprocessing — deliberately not pursued. An
  estimate suggested a ~4x speedup ceiling (bound by CPU core count,
  since checking is CPU bound and Python’s Global Interpreter Lock (GIL) prevents threading
  from helping). Judged not worth the complexity given current scale,
  and the diminishing-cost trajectory as checkers share a single
  parse. Revisit if real usage patterns show this actually matters.
- A Rust rewrite of the checker core (the ruff approach) — explicitly
  out of scope. Would be pursued for learning purposes rather than a
  demonstrated performance need, and is a fundamentally larger
  undertaking than anything else on this list.
