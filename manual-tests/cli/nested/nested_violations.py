"""A nested manual-test fixture."""


def nested_function(value: int, other: int) -> int:
    """Trigger PYR402 during recursive directory testing."""
    return value + other
