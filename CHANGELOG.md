# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project is in the `0.x` series, so minor version bumps do not
carry the same backward-compatibility guarantee they would after
`1.0.0`. Patch bumps are the default for incremental changes. Minor
bumps are reserved for changes that shift what pyrigor
is usable for.

## [Unreleased]

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

## [0.2.3] 2026-08-13

### Fixed

- `site-packages` directories are now excluded by default during
  directory walks, regardless of the containing venv folder’s own
  name.
- A single unreadable or unparseable file no longer crashes the run.
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
