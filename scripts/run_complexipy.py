"""A cross-platform wrapper forcing UTF-8 mode before invoking complexipy.

The tool complexipy's own console output (via rich) assumes UTF-8-capable
output and crashes on Windows' legacy cp1252 codepage when printing
status emoji. Setting PYTHONUTF8 before the subprocess starts avoids
this without depending on shell-specific quoting.
"""

import os
import subprocess  # nosec -- fixed, local complexipy invocation only
import sys


def main() -> None:
    """Run complexipy with UTF-8 mode forced, forwarding all CLI arguments."""
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"

    # noinspection PyArgumentEqualDefault
    result = subprocess.run(["complexipy", *sys.argv[1:]], env=env, check=False)  # nosec # noqa: S603, S607
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
