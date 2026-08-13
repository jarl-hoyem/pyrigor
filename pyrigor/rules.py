"""Registry of all pyrigor rules.

Each Rule member's name is the rule's code (for example, PYR402), and its
value is the rule's symbolic name (for example, "keyword-only-arguments") —
matching the pylint-style dual-identifier convention pyrigor's own
output and suppression comments use.
"""

from enum import Enum


# pyrigor/rules.py
class Rule(Enum):
    """All pyrigor rules implemented or planned."""

    PYR401 = "namedtuple-returns"
    PYR402 = "keyword-only-arguments"

    @property
    def problem(self) -> str:
        """The rule-specific problem description, for violation messages."""
        return _RULE_PROBLEMS[self]


_RULE_PROBLEMS: dict[Rule, str] = {
    Rule.PYR401: "returns a bare multi-value tuple; use a NamedTuple instead",
    Rule.PYR402: "has positional parameters; all parameters should be keyword-only",
}
