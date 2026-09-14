"""Check that whole-project tools exclude every generated or vendored directory.

The mypy and ty checkers read .gitignore themselves. The tools radon, xenon,
vulture and pyright cannot, so each keeps its own list. This check stops those
lists drifting apart.
"""

import tomllib
from pathlib import Path
from typing import Final

from dev_tooling_shared import PRE_COMMIT_CONFIG, PYPROJECT_TOML

_EXCLUDE_TOKENS: Final = (".venv", "dist", "htmlcov", "egg-info", "mutants", "__pycache__")
_LITERAL_LIST_HOOKS: Final = ("radon-maintainability", "xenon", "vulture")
_GITIGNORE_FLAG: Final = "--exclude-gitignore"


def hook_block(*, config_text: str, hook_id: str) -> str:
    """Return one hook's configuration without its comment lines.

    Args:
        config_text: Contents of the pre-commit configuration file.
        hook_id: The hook's `id:` value.

    Returns:
        The hook's lines up to the next hook, or an empty string when the hook is absent.
    """
    marker = f"- id: {hook_id}\n"
    start = config_text.find(marker)
    if start == -1:
        return ""
    end = config_text.find("- id: ", start + len(marker))
    block = config_text[start:] if end == -1 else config_text[start:end]
    return "\n".join(line for line in block.splitlines() if not line.lstrip().startswith("#"))


def _hook_problems(*, config_text: str) -> list[str]:
    """Return a message for each canonical directory a literal-list hook does not exclude.

    Args:
        config_text: Contents of the pre-commit configuration file.

    Returns:
        One message per missing directory, grouped by hook.
    """
    problems: list[str] = []
    for hook_id in _LITERAL_LIST_HOOKS:
        block = hook_block(config_text=config_text, hook_id=hook_id)
        problems.extend(f"{hook_id} does not exclude {token}" for token in _EXCLUDE_TOKENS if token not in block)
    return problems


def _pyright_problems(*, pyproject_text: str) -> list[str]:
    """Return a message for each canonical directory missing from pyright's exclude list.

    Args:
        pyproject_text: Contents of pyproject.toml.

    Returns:
        One message per missing directory.
    """
    excludes = " ".join(tomllib.loads(pyproject_text).get("tool", {}).get("pyright", {}).get("exclude", []))
    return [f"pyright does not exclude {token}" for token in _EXCLUDE_TOKENS if token not in excludes]


def find_problems(*, config_text: str, pyproject_text: str) -> list[str]:
    """Return one message for each tool that misses part of the canonical exclusion set.

    Args:
        config_text: Contents of the pre-commit configuration file.
        pyproject_text: Contents of pyproject.toml.

    Returns:
        A message per missing exclusion. The list is empty when every tool is in sync.
    """
    problems = _hook_problems(config_text=config_text) + _pyright_problems(pyproject_text=pyproject_text)
    if _GITIGNORE_FLAG not in hook_block(config_text=config_text, hook_id="mypy"):
        problems.append(f"mypy does not pass {_GITIGNORE_FLAG}")
    return problems


def main() -> int:
    """Print every missing exclusion, failing when there is at least one."""
    problems = find_problems(
        config_text=Path(PRE_COMMIT_CONFIG).read_text(encoding="utf-8"),
        pyproject_text=Path(PYPROJECT_TOML).read_text(encoding="utf-8"),
    )
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
