"""A file containing a deliberately suppressed diagnostic."""


def apply_correction(weight: int, bias: int) -> int:  # pyrigor PYR402 # manual test
    """Use positional parameters for suppression testing."""
    return weight + bias
