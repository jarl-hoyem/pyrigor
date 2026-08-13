"""Tests for pyrigor's Rule registry."""

from pyrigor.rules import Rule


def test_pyr402_rule_has_correct_code_and_name() -> None:
    """Rule PYR402's name/symbolic_name should match the expected code and name."""
    assert Rule.PYR402.name == "PYR402"
    assert Rule.PYR402.symbolic_name == "keyword-only-arguments"
