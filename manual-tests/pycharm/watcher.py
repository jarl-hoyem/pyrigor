"""A file producing violations at several columns, for watcher checks."""

from contextlib import suppress


def make_pair() -> tuple[int, str]:
    """Return two values without a NamedTuple."""
    return 2, "two"


def apply_correction(weight: int, bias: int) -> int:
    """Use the positional parameters and return a value."""
    return weight + bias


def discard_result() -> int:
    """Return a value that callers should use."""
    return 3


def run() -> None:
    """Discard return values at two different indent depths."""
    apply_correction(1, 2)
    with suppress(ValueError):
        discard_result()
