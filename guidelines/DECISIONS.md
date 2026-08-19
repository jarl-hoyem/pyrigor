# Design and architecture decisions

A running log of *why* a structural choice was made, not just the
result. Read this before asking "why does the code do it this way"
rather than re-deriving the reasoning from scratch.

## pyrigor architecture and rules

### NamedTuple and NewType close different gaps

NamedTuple for returns, NewType for same-typed values at risk of confusion.

Rule:

Always use NamedTuple for any function returning more than one
value. This removes positional-unpacking ambiguity. The caller
accesses fields by name (result.dj_dw), not position, so a
mislabeled variable at the call site can no longer silently receive
the wrong value.

Use NewType for any same-typed values, whether function arguments or
NamedTuple fields, that could plausibly be swapped or confused (for
example, Weight/Bias when both might be represented as float or a
same-shaped ndarray). Skip it where confusion is not realistically
possible.

Why:

Different-typed arguments (for example, w: np.ndarray, b: float) are
already protected by mypy, a swap at the call site is a type
mismatch and gets caught. No NewType needed here.

Same-typed arguments (for example, two float parameters) are not
protected by mypy alone. Both are structurally identical, so a swap
is a silent, valid-looking call. NewType makes them nominally
distinct, so mypy catches the swap.

NamedTuple closes a separate gap: even with a fully typed
multi-value return (for example, tuple[np.ndarray, float]), mypy
checks the type at each position but not the name the caller gives
it. A caller can unpack into misleadingly named variables
(dj_db_temp, dj_dw_temp = ... when the function actually returns
dj_dw, dj_db), and mypy will not catch it, because the types still
line up positionally, only the semantics are wrong. This is a silent
bug that surfaces only when the mislabeled variable is later used in
a way that exposes its true type. For example, calling '.tolist()' on
an assumed float, a runtime crash, not a caught error.

NamedTuple field access removes the positional slot entirely, so
there is nothing to mislabel.

Combined, these two will catch:

- Argument-order swaps for differently typed args: plain type
  annotations (no extra tooling needed).
- Argument-order swaps for same-typed args: NewType.
- Return-unpacking mislabeling for differently typed return values:
  NamedTuple alone.
- Return-unpacking mislabeling for same-typed return fields:
  NamedTuple and NewType together.

Example:

```python
class GradientResult(NamedTuple):
    dj_dw: Weight
    dj_db: Bias

def compute_gradient_logistic(x: np.ndarray, y: np.ndarray, w: Weight, b: Bias) -> GradientResult:
    ...
    return GradientResult(dj_dw=dj_dw, dj_db=dj_db)
```

### Shared AST walk instead of per-checker walking, and why a cache was rejected

Every checker originally called `ast.walk(tree)` independently, once
per checker per the file. Profiling against the Home Assistant core
(18,187 files) found this was the dominant cost: `ast.walk` itself
accounted for 286 of 388 seconds, and the cost scaled linearly with
the number of registered checkers, every future rule added would
make it worse.

Two designs were considered.

**Cache-based** (rejected): keep every checker’s own
`find_violations(*, tree)` signature exactly as-is, walk once inside
`_run_checkers`, and cache the result keyed by `id(tree)`, so a
repeated internal `ast.walk` call inside `_shared.py` would hit the
cache rather than re-walking. Smaller diff, no signature changes
anywhere. Rejected because it is exactly the kind of implicit,
hidden coupling this project has repeatedly been burned by — the
`zip(CHECKERS, Rule)` positional-coupling bug fixed earlier is the
same category of problems. It rests on an unenforced assumption:
"every checker always walks the same cached tree." It also does not
remove the actual walk cost — it only hides one walk behind a
cache lookup. Real savings would require every future checker’s own
logic to want the tree walked in the same way, silently broken
the moment one does not.

**Nodes-based** (chosen): walk the tree exactly once in
`_run_checkers`, via `walk_once()`, producing a `WalkedNodes(
function_nodes, assign_nodes)`. Every checker’s own public
`find_violations` signature changes from `(*, tree: ast.Module)` to
`(*, nodes: WalkedNodes)`, an honest interface describing exactly
what each checker actually needs, rather than "a tree, which happens
to be pre-walked somewhere else by convention." Real cost: touched
five checker files, the `_CheckerFun` Protocol, and every existing
test calling `find_violations` directly. Real result: confirmed via
profiling, `ast.walk`'s own call count dropped exactly 5.0x
(69,393,100 to 13,878,620), and real-world timing on the same
18,187-file run dropped from 388.20 s to 55.46 s, 7x.

### PYR406 matches only bare-name calls, not attribute calls

PYR406 flags a discarded call only when the callee is a bare name
(`compute_total(items)`), never through attribute access
(`self.compute_total()`, `obj.compute_total()`). Consequently,
functions with a leading `self`/`cls` parameter (methods) are
excluded from the protected set entirely.

Why: pyrigor cannot reliably determine which class or object an
attribute call belongs to — it has no type inference and
processes one file at a time. Without this exclusion, matching
by name alone would let a method’s name enter the protected set
even though nothing ever calls it as a bare name. The only effect would be
a false positive on some unrelated bare call elsewhere in the file
that happens to share the method’s name. Excluding likely methods
removes that risk at the cost of not covering method calls at all,
consistent with the guideline doc’s own examples, which are all
bare-name, module-level or nested function calls.

## Development process and tooling

### The tool complexipy runs through a Python wrapper, not a .bat script

The tool complexipy’s own console output (via `rich`) crashes on Windows’
legacy `cp1252` codepage when printing status emoji, confirmed
across two different pinned versions (an octopus at v3.0.0, a
checkmark at v7.0.1), a genuine, systemic upstream bug, not fixed
between releases.

A Windows batch script (`scripts/run_complexipy.bat` setting
`PYTHONUTF8=1` before invoking the binary) was considered first, and
would have worked locally. Rejected because it is Windows-only,
`.bat` syntax and `%*` argument forwarding mean nothing on macOS or
Linux, and this project’s own CI matrix explicitly tests
`ubuntu-latest`, `macos-latest`, and `windows-latest`. A fix that
only works for one contributor’s own OS is not a real fix for a
project with a genuinely cross-platform CI matrix.

Chosen instead: `scripts/run_complexipy.py`, a Python wrapper
setting `PYTHONUTF8` via `os.environ` before invoking `complexipy`
as a subprocess. Works identically on every OS `language: python`
already guarantees a Python interpreter for, no shell-specific
quoting or syntax involved.

### The tool pyrigor runs two self-checks, pinned and local, not just one

A single self-check, running only the current local/uncommitted
code, would never actually prove the *released, installable* package
works the way an external adopting project would use it, real
packaging or manifest issues (like `.pre-commit-hooks.yaml` being
missing from a given release, found and fixed this session) would go
undetected. A single self-check running only the pinned, released
version would lose the opposite, real, proven value: pyrigor’s own
new rules have repeatedly caught real bugs in pyrigor’s own
in-progress source the moment they were built, before any release
existed. Kept both, deliberately, rather than choosing one.

### Pyrigor’s suppression comment must come last when stacked with another tool’s

The regular expression in `_suppressed_tokens()` (`#\s*pyrigor\s*:\s*(?P<tokens>.+)$`)
captures everything after `# pyrigor:` to the end of the line as the
reason. Stacking another tool’s suppression comment (`# nosec`,
`# complexipy: ignore`) after pyrigor’s own gets silently absorbed
into that reason text, since `body.partition("#")` only splits once.

Considered fixing the parser instead, truncating the reason at the
next `#` regardless of what follows. Rejected — this would break a
legitimate case: a reason referencing a GitHub issue number, for
example `# pyrigor: 406 # see issue #42`. Truncating trades away real
information to guard against a risk that, checked directly, has no
current observable effect. The function `filter_suppressed()` never
reads a reason’s content, only checks whether it is None.

Chosen instead: a house convention, not a code change. Pyrigor’s own
suppression comment goes last when stacked with another tool’s
(`# nosec  # pyrigor: PYR402 # reason`, not the reverse). The
opposite ordering already works correctly, since `re.search` finds
`# pyrigor:` wherever it appears on the line — this convention costs
nothing beyond documenting it.

### Suppression scanning uses tokenizing, not raw-line regular expression

`_suppressed_tokens()` and the near-miss check both used to search
each candidate physical line’s raw text via regular expression
(`_SUPPRESSION_PATTERN`, `_NEAR_MISS_PATTERN`), with no awareness of
Python’s lexical structure. A string literal or docstring whose
contents happened to exactly match `# pyrigor: CODE # reason` syntax
would not just trigger a spurious near-miss warning — it could
silently suppress a real violation on that line, since regular expression over
raw text cannot tell a genuine comment from text that merely looks
like one inside a string. Found scanning `tests/` for the first
time: a near-miss warning fired on a test’s own fixture string
containing literal `# pyrigor` text, not a real comment (#41).

Chosen fix: tokenize the source once per every file with Python’s own
`tokenize` module, and build a line-number-to-comment-text mapping
from genuine `tokenize.COMMENT` tokens only. String and docstring
content is tokenized as `STRING`, never `COMMENT`, so text that only
looks like a suppression comment inside a string can no longer match
at all. Candidate-line lookup changed from list-indexing raw source
lines to a dict lookup on this map, which also removes the need for
the old `_line_at()`’s explicit out-of-range bounds check — a
missing dict key returns "", the same "no comment here"
result an out-of-range line used to require special-casing for.

Rejected: keeping the regular expression approach and trying to special-case
strings within it (for example, stripping string literals from each
line before searching). Would need to reimplement a real Python
tokenizer piecemeal to handle multi-line strings, f-strings and
escaped quotes correctly — strictly more code and later risk than
just using the tokenizer the standard library already provides for
exactly this purpose.

## The magic_value pylint extension: Real, independent corroboration of PYR203’s boundary

Enabled in pyrigor’s own pyproject.toml. Default valid-magic-values
(0, –1, 1, "", "__main__") match PYR203’s own chosen exemption
list (0, 1, –1) independently. Real corroboration of the boundary is
reasonable, not an accident. Narrower scope than PYR203, though,
only fires on comparisons (if x == 3), not arithmetic or function
arguments.

Kept running even once PYR203 ships, deliberately, not disabled.
The same precedent is already established in this project: mypy, pyright
and ty all run simultaneously despite real overlap in what they
catch, genuine defense in depth from independent implementations,
not wasted duplication.
