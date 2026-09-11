"""Check that Prettier is pinned to the same version in both places it appears.

The pre-commit hook bootstraps its own copy through `additional_dependencies`,
so that CI and a fresh clone need no Node setup. The IDE resolves Prettier from
`node_modules`, so that formatting on save matches the hook. Two copies means
two pins, and nothing else stops them drifting apart.
"""

import json
import re
from pathlib import Path
from typing import NamedTuple

PRE_COMMIT_CONFIG = Path(".pre-commit-config.yaml")
PACKAGE_JSON = Path("package.json")
_HOOK_PIN = re.compile(r"prettier@(?P<version>\d+[.]\d+[.]\d+)")


class PrettierPins(NamedTuple):
    """The Prettier version pinned in each file that names one."""

    hook: str | None
    package: str | None


def read_pins(*, config_text: str, package_text: str) -> PrettierPins:
    """Return the Prettier version pinned in the pre-commit config and in package.json.

    Args:
        config_text: Contents of the pre-commit configuration file.
        package_text: Contents of package.json.

    Returns:
        The two pinned versions. Each is None when its file does not name one.
    """
    match = _HOOK_PIN.search(config_text)
    package = json.loads(package_text).get("devDependencies", {}).get("prettier")
    return PrettierPins(hook=match.group("version") if match else None, package=package)


def main() -> int:
    """Compare the two pins and report any disagreement."""
    pins = read_pins(
        config_text=PRE_COMMIT_CONFIG.read_text(encoding="utf-8"),
        package_text=PACKAGE_JSON.read_text(encoding="utf-8"),
    )
    if pins.hook == pins.package:
        return 0
    print(f"Prettier pin mismatch: {PRE_COMMIT_CONFIG} has {pins.hook}, {PACKAGE_JSON} has {pins.package}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
