"""Tests that Rule enum members and guidelines/ docs stay in sync."""

import re
from pathlib import Path

import pytest

from pyrigor.checkers import CHECKERS
from pyrigor.rules import Rule

GUIDELINES_DIR = Path(__file__).parent.parent / "guidelines"


def test_every_rule_has_a_matching_guideline_file() -> None:
    """Each Rule member should have exactly one guideline/PYR xxx-<symbolic-name>.md file."""
    if not GUIDELINES_DIR.exists():
        pytest.skip("Guidelines directory not found (likely running under mutmut in mutants/ directory)")

    for rule in Rule:
        expected_path = GUIDELINES_DIR / f"{rule.name}-{rule.symbolic_name}.md"
        assert expected_path.exists(), f"Missing or misnamed guideline file: {expected_path.name}"


def _assert_fix_availability_matches(*, rule: Rule, guideline: str) -> None:
    """Assert one rule's guideline states the same fix availability as its metadata."""
    match = re.search(r"## Fix classification\s+[*]{2}Fix availability:[*]{2} `(?P<fix_availability>[^`]+)`", guideline)
    assert match is not None, f"Missing fix availability in {rule.name}'s guideline"
    assert match.group("fix_availability") == rule.fix_availability.value, f"Fix availability drifted for {rule.name}"


def _assert_applicability_matches(*, rule: Rule, guideline: str) -> None:
    """Assert one rule's guideline states the same applicability as its metadata or states none."""
    match = re.search(
        r"## Fix classification.*?[*]{2}Applicability:[*]{2} `(?P<applicability>[^`]+)`", guideline, re.DOTALL
    )
    if rule.applicability is None:
        assert match is None, f"{rule.name} has no applicability, but its guideline states one"
    else:
        assert match is not None, f"Missing applicability in {rule.name}'s guideline"
        assert match.group("applicability") == rule.applicability.value, f"Applicability drifted for {rule.name}"


def test_implemented_rule_fix_classification_matches_its_guideline() -> None:
    """Every implemented rule's canonical fix availability and applicability match its guideline document."""
    if not GUIDELINES_DIR.exists():
        pytest.skip("Guidelines directory not found (likely running under mutmut in mutants/ directory)")

    for registered_checker in CHECKERS:
        rule = registered_checker.rule
        guideline = (GUIDELINES_DIR / f"{rule.name}-{rule.symbolic_name}.md").read_text(encoding="utf-8")
        _assert_fix_availability_matches(rule=rule, guideline=guideline)
        _assert_applicability_matches(rule=rule, guideline=guideline)
