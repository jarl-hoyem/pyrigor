# Rejected rules

Rules that were considered, and not built — either because an
existing tool already covers the pattern, or because the pattern
cannot be checked without an unacceptable false-positive rate.
Pyrigor exists to fill gaps other tools miss, not
to re-implement checks they already do well (see
[`ADDING_A_RULE.md`](./ADDING_A_RULE.md), step 0). This document is
the audit trail, so a rejected idea does not get silently rebuilt or
re-debated from scratch later.

Entries here are not permanent. If a project stops using the
covering tool, or the covering tool’s check turns out to have a real
gap of its own, a rejected rule can be revisited. Note why
revisiting if that happens.

## PYR404 — Mutable default argument values

Would have mandated `None` defaults over mutable ones
(`def f(items: list = []):`). A full guideline doc was written before
this overlap was found.

**Covered by**: ruff's `B006` (flake8-bugbear,
mutable-argument-default) and pylint's `W0102`
(dangerous-default-value). Both already run in pyrigor’s own
pre-commit stack and in any project following pyrigor’s own
`CONTRIBUTING.md` tooling recommendations.

**Status**: guideline doc kept for now
(`guidelines/PYR404-immutable-defaults.md`) as documentation of the
reasoning, marked as not independently enforced by pyrigor and
covered elsewhere. The rule number PYR404 remains reserved and
should not be reused for a different rule.

## Non-atomic mutation under free-threading (PEP 703)

Would have flagged patterns like `self.counter += 1` as unsafe under
free-threaded (no-GIL) Python, since such an increment is not atomic
the way e.g. `list.append` is.

**Rejected because**: not a tool-overlap case like the others in
this document — no existing tool would catch this either. Rejected
on false-positive grounds instead. `self.x += 1` is one of the most
common idioms in ordinary, single-threaded Python; flagging it
unconditionally would be almost entirely noise, and there is no way
to tell from AST alone whether a given class is ever shared across
threads under a free-threaded build. Detecting the real risk would
require actual concurrency analysis, not a local AST pattern.

**Source**: filed as [#37](https://github.com/jarl-hoyem/pyrigor/issues/37),
itself sourced from the Python Podcast's ["Python 3.13"](https://python-podcast.de/show/python-313/)
episode (2024-11-12).

**Status**: no guideline doc was ever written; rejected before that
step per `ADDING_A_RULE.md` step 0's overlap/feasibility check.

## Not yet rejected, flagged as likely overlapping

These have not had a guideline doc written, specifically because the
overlap check in `ADDING_A_RULE.md` step 0 was applied before
writing one. Listed here rather than in `BACKLOG.md`'s general list,
to keep the "likely already covered" reasoning visible alongside the
confirmed rejection above.

- **No wildcard imports** — covered by the ruff's `F403`/`F405` and
  pylint's `W0401`.
- **Required return type annotations** — covered by mypy's
  `--disallow-untyped-defs` (part of `--strict`, already assumed as
  pyrigor’s baseline per PYR401’s own "Detection scope" section) and
  ruff's `ANN` rule family, if enabled.
- **Timezone-aware datetime construction** — covered by ruff's `DTZ`
  rule family (flake8-datetimez), if enabled.
- **Mandate `StrEnum` over plain `Enum` when a state crosses a
  string-typed boundary** — considered alongside PYR202’s own
  `Literal`/`StrEnum` discussion. Picking plain `Enum` where
  `StrEnum` would help fails early (`TypeError` on serialization,
  or a mypy type mismatch at the call site), not silently — the
  opposite of the failure class PYR202 itself targets. Detecting it
  would also need real cross-site usage analysis (does this `Enum`
  ever meet a string boundary elsewhere), not a local AST pattern —
  the same category of problems as the already-backlogged, opt-in
  astroid experiment, not a default mandatory rule.
