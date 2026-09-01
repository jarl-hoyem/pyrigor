"""A clean file for manual CLI tests."""

# pylint: disable=duplicate-code  # Minimal standalone fixture intentionally mirrors test inputs.


def add(*, left: int, right: int) -> int:
    """Add two values."""
    return left + right
