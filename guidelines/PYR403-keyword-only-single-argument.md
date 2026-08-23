# PYR403 — Use keyword-only arguments even for single-parameter functions

## Rule

A function with exactly one parameter must still use a bare `*` to
make that parameter keyword-only. This is a separate, independently
adoptable rule from [PYR402](PYR402-keyword-only-arguments.md), not
a stricter mode of it — a project may adopt PYR402 alone, PYR403
alone, or both.

```python
# Bad
def main(paths: list[str]) -> int:
    ...

# Good
def main(*, paths: list[str]) -> int:
    ...
```

## Rationale

[PYR402](PYR402-keyword-only-arguments.md) exists primarily to
prevent argument-order confusion — a concern that
requires two or more parameters. A single-parameter function has no
order to get wrong. That is why PYR402 explicitly exempts it.

But argument-order confusion is not the only way a positional call
goes wrong. A single-parameter function can still be called with the
*wrong value entirely* — not swapped against a sibling argument, but
still the wrong variable, passed by mistake:

```python
def main(paths: list[str]) -> int:
    ...

# Both are lists of strings. Nothing about the call site indicates
# what `changed_files` actually is, or confirms it's the right thing
# to pass here. This compiles, type-checks, and is silently wrong if
# `changed_files` was not what main() was meant to receive.
main(changed_files)
```

A keyword-only call forces the call site to name what it is passing,
turning an anonymous positional argument into a small, explicit
self-check at the point of writing and at every point of reading it
again later:

```python
def main(*, paths: list[str]) -> int:
    ...

main(paths=changed_files)
```

This is the same "human readability at the point of writing" argument
[PYR402](PYR402-keyword-only-arguments.md) makes as one of several
reasons to adopt it — PYR403 isolates that argument on its own,
because it is the *only* one of PYR402's reasons that still applies
when there is only one parameter, and it is a real but comparatively
low-value protection: milder than the swap protection PYR402 provides
for multi-parameter functions, and the marginal benefit on a call
site that's already obvious from context (a well-named single
variable passed to a well-named single parameter) can be small.

This asymmetry is exactly why PYR403 is a separate, opt-in rule
rather than folded into PYR402 itself: applying it universally risks
flagging code a competent reader would immediately recognize as safe
(a private, single-argument helper called from one obvious call
site), and rules that fire on obviously safe code erode trust in a
linter faster than almost anything else. A team that values the
self-documentation benefit enough to pay that cost everywhere can
adopt PYR403 explicitly. A team that does not value it can adopt PYR402 alone
without missing out on genuine swap protection.

## Fix classification

**Kind:** `safe_fix`

**Reasoning:** The same reasoning as
[PYR402](./PYR402-keyword-only-arguments.md): mechanical and
correct, and any caller consequence is immediate and loud via
mypy/pyright, not silent. Per #105's own adopted classification.

## When this does not apply

- Functions with zero parameters — nothing to name.
- Functions with two or more parameters — that is
  [PYR402](PYR402-keyword-only-arguments.md)’s territory, not
  PYR403’s.
- The same exceptions [PYR402](PYR402-keyword-only-arguments.md)
  lists apply here too: established positional conventions from a
  wrapped library or `dataclass`-generated code, and profiled hot
  paths where keyword-argument binding overhead has been shown to
  matter.

## Related

- [PYR402](PYR402-keyword-only-arguments.md) — force keyword-only
  arguments for functions with two or more parameters. PYR402 and
  PYR403 are independent, adoptable alone or together.

## Enforced by

The `pyr403` checker (`pyrigor/checkers/pyr403_keyword_only_single_argument.py`),
wired in as a pre-commit hook and available via the `pyrigor` CLI
(`pip install pyrigor`, then `pyrigor path/to/file.py`).
