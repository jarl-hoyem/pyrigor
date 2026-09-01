# Use the native shell on Windows; Unix keeps just's default POSIX shell.
[windows]
set shell := ["powershell.exe", "-NoLogo", "-Command"]

# Development tasks for pyrigor

# Setup: install dependencies and pre-commit hooks
setup:
    uv sync --extra dev
    uv run pre-commit install

# Run pyrigor on a file or directory
pyrigor path="pyrigor":
    uv run pyrigor {{path}}

# Run pyrigor with specific rules (by code, number, or name)
pyrigor-select rules path="pyrigor":
    uv run pyrigor --select={{rules}} {{path}}

# Run pyrigor excluding specific rules
pyrigor-ignore rules path="pyrigor":
    uv run pyrigor --ignore={{rules}} {{path}}

# Show pyrigor version
version:
    uv run pyrigor --version

# Run full test suite with coverage
test:
    uv run pytest

# Run tests in a single file
test-file file:
    uv run pytest {{file}}

# Run a single test by name
test-single file test:
    uv run pytest {{file}}::{{test}}

# Run slow tests (deselected by default)
test-slow:
    uv run pytest -m slow

# Run all quality gates (pre-commit or pre-push stage)
check stage="pre-commit":
    uv run pre-commit run --all-files --hook-stage {{stage}}

# Run PyCharm inspections in Docker (requires Docker)
inspect:
    .\scripts\run_pycharm_inspection_docker.ps1

# Run mutation tests in Docker (requires Docker)
mutmut:
    .\scripts\run_mutmut_docker.ps1

# Type-check with mypy
mypy:
    uv run mypy .

# Type-check with pyright
pyright:
    uv run pyright --project=pyproject.toml

# Type-check with ty
ty:
    uv run ty check .

# Check code with ruff
ruff-check:
    uv run ruff check

# Format code with ruff
ruff-format:
    uv run ruff format

# Show all available recipes
help:
    just --list
