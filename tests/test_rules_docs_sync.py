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


def test_implemented_rule_fixability_matches_its_guideline() -> None:
    """Every implemented rule's canonical fixability matches its guideline document."""
    if not GUIDELINES_DIR.exists():
        pytest.skip("Guidelines directory not found (likely running under mutmut in mutants/ directory)")

    for registered_checker in CHECKERS:
        rule = registered_checker.rule
        guideline = (GUIDELINES_DIR / f"{rule.name}-{rule.symbolic_name}.md").read_text(encoding="utf-8")
        match = re.search(r"## Fix classification\s+[*]{2}Kind:[*]{2} `(?P<fixability>[^`]+)`", guideline)
        assert match is not None, f"Missing fix classification in {rule.name}'s guideline"
        assert match.group("fixability") == rule.fixability.value, f"Fixability drifted for {rule.name}"
