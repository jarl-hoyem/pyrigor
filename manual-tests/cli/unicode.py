# ruff: noqa: PLC2401
# pylint: disable=non-ascii-name
"""A file for checking Unicode source locations."""


# noinspection NonAsciiCharacters
def café(weight: int, bias: int) -> int:
    """Use a non-ASCII identifier before a violation."""
    return weight + bias
