# Contributing to pyrigor

Contributions are welcome!

## Creating Issues

- Use the issue template if one exists.
- Provide a clear description and reproduction steps (for bugs).
- Label the issue (type) if you can.

## Sizing Issues

Effort and value are labeled `effort: XS` through `effort: L`, and
`value: XS` through `value: L`. There is no `XL`. If a piece of work
is genuinely larger than `L`, it does not get an `XL` label, instead:

1. Create a planning issue for it, sized whatever actually fits
   (`S` or `M`, describing the planning work itself, not the
   effort).
2. In that planning issue, split the real work into smaller, linked
   issues, each sized normally.

An `XL`-sized issue is a sign the work has not been broken down
enough yet, not a size to label and leave as one item.

## Labels

Beyond `value:`/`effort:` (see sizing above) and a type label,
check every issue against the full label set before finalizing, not
just the three required minimums:

`priority`, `pending other work`, `testing`,
`technical debt / refactoring`, `good first issue`, `pedantic`,
`documentation`, `tooling`, `rule in pyrigor`, and GitHub’s own defaults
(`bug`, `enhancement`, `duplicate`, `invalid`, `wontfix`, `question`,
`help wanted`). Multiple labels commonly apply at once, a type label
plus `technical dept / refactoring` is a normal, expected
combination, not redundant.

## Branching Strategy

1. **All changes start with an issue.**
2. **Branch naming:** `<issue-number>-<brief-description>` where applicable, for example   `12-fix-pyr001-docstring`.
3. **Never commit directly to `main`.**
4. **Open a Pull Request** from the branch.
5. **Delete the branch** after merge.

## Development Setup

The tool pyrigor targets Python 3.11+ (see `pyproject.toml` for the current floor and the
supported-version policy). Development uses [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/jarl-hoyem/pyrigor.git
cd pyrigor
uv sync --extra dev
pre-commit install
```

`pre-commit install` sets up both the pre-commit and commit-msg hooks in one step
(configured via `default_install_hook_types` in `.pre-commit-config.yaml`).

A `dod-check` pre-commit hook prints warn-only notes (never blocks a
commit) if a version bump or checker change looks like it might be
missing a matching documentation update. See
[`guidelines/DEFINITION_OF_DONE.md`](./guidelines/DEFINITION_OF_DONE.md).

See [`guidelines/DEFINITION_OF_DONE.md`](./guidelines/DEFINITION_OF_DONE.md)
for the standing checklist applied before any change is considered
finished, and [`guidelines/REVIEW_CHECKLIST.md`](./guidelines/REVIEW_CHECKLIST.md)
for the earned, defect-derived checklist alongside it.

## Self-hosted pre-commit hook

The tool pyrigor checks itself two ways, deliberately: a pinned entry
(`repo: https://github.com/jarl-hoyem/pyrigor`, `rev: vX.Y.Z`)
running the last real, released version, and a local entry running
today’s uncommitted code. The local entry is the one that matters
day to day. It is what catches a new rule firing on pyrigor’s own
source the moment it is built, before any release exists. The pinned
entry exists mainly to confirm the released package genuinely works
as a real, external hook would use it.

`scripts/version_sync.py` runs on every commit and does nothing
unless `pyproject.toml`'s version just changed. If it did, it runs
`pre-commit autoupdate` and `uv lock`, then deliberately fails the
commit so any resulting changes (a refreshed hook pin, an updated
lockfile) get staged and committed, rather than left behind
unstaged. Note: when the release commit itself, the new
tag does not exist yet, so this only catches up starting with the
next commit after a release, not the release commit itself.

## Before Submitting a Pull Request

- Run all pre-commit checks: `pre-commit run --all-files`
- Ensure tests pass: `uv run pytest`
- Add tests for new features — **100% coverage is enforced** (`--cov-fail-under=100`,
  branch coverage included) on every commit.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`type: description`), enforced by the `commitizen` pre-commit hook

## Code Style

- `ruff` (lint) and `ruff-format` (formatting) — no `black`
- `pylint`, `mypy`, `pyright`, and `ty` (strict mode, all three type checkers)
- Google-style docstrings (`pydocstyle`)
- Type hints required
- See the `guidelines/` folder for pyrigor’s own coding-discipline rules
  (`PYRxxx`) — these apply to pyrigor’s own source too.

## Questions?

Open an issue on GitHub.
