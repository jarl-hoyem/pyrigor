"""Tests that Rule enum members and guidelines/ docs stay structurally in sync."""

from pathlib import Path

from pyrigor.rules import Rule

GUIDELINES_DIR = Path(__file__).parent.parent / "guidelines"


def test_every_rule_has_a_matching_guideline_file() -> None:
    """Each Rule member should have exactly one guideline/PYR xxx-<symbolic-name>.md file."""
    for rule in Rule:
        expected_path = GUIDELINES_DIR / f"{rule.name}-{rule.symbolic_name}.md"
        assert expected_path.exists(), f"Missing or misnamed guideline file: {expected_path.name}"
