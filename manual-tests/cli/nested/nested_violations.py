"""A recursive-directory manual-test fixture."""


def recursive_fixture(value: int, other: int) -> int:
    """Trigger PYR402 while testing recursive directory discovery."""
    return value + other
