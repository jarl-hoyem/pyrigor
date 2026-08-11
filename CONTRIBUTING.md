# Contributing to pyrigor

Contributions are welcome!

## Creating Issues

- Use the issue template if one exists.
- Provide a clear description and reproduction steps (for bugs).
- Label the issue (type) if you can.

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
