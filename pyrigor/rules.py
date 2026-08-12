"""Registry of all pyrigor rules.

Each Rule member's name is the rule's code (for example, PYR402), and its
value is the rule's symbolic name (for example, "keyword-only-arguments") —
matching the pylint-style dual-identifier convention pyrigor's own
output and suppression comments use.
"""

from enum import Enum


class Rule(Enum):
    """All pyrigor rules implemented or planned."""

    PYR402 = "keyword-only-arguments"
