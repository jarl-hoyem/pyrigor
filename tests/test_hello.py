"""Smoke test for the pyrigor package."""

from pyrigor import hello


def test_hello() -> None:
    """hello() should return a non-empty greeting mentioning pyrigor."""
    result = hello()
    assert "pyrigor" in result
