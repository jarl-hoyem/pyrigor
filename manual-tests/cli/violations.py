"""A file containing representative pyrigor violations."""

from typing import Any


def make_pair() -> tuple[int, str]:
    """Return the two values without a NamedTuple."""
    return 1, "one"


def apply_correction(weight: int, bias: int) -> int:
    """Use the positional parameters and return a value."""
    return weight + bias


def discard_result() -> int:
    """Return a value that callers should use."""
    return 1


def run() -> None:
    """Trigger the representative diagnostics."""
    apply_correction(1, 2)
    discard_result()


unused_pair: Any = make_pair
