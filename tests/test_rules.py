"""Tests for pyrigor's Rule registry."""
# test assertions compare against expected literal values by design,
# not a magic-value problem
# pylint: disable=magic-value-comparison

from pyrigor.rules import Rule, Severity


def test_pyr402_rule_has_correct_code_and_name() -> None:
    """Rule PYR402's name/symbolic_name should match the expected code and name."""
    assert Rule.PYR402.name == "PYR402"
    assert Rule.PYR402.symbolic_name == "keyword-only-arguments"


def test_pyr402_rule_has_warning_severity() -> None:
    """Rule PYR402 (a defense-in-depth, mypy/pyright-backed rule) should be WARNING severity."""
    assert Rule.PYR402.severity == Severity.WARNING


def test_pyr406_rule_has_error_severity() -> None:
    """Rule PYR406 (a genuinely silent, discarded-value bug) should be ERROR severity."""
    assert Rule.PYR406.severity == Severity.ERROR


def test_severity_values_match_lsp_naming() -> None:
    """Severity's string values should match LSP's own DiagnosticSeverity naming, for #159's future JSON output."""
    assert Severity.ERROR.value == "error"
    assert Severity.WARNING.value == "warning"
    assert Severity.INFO.value == "info"
