"""Registry of all pyrigor rules.

Each Rule member's value is a RuleInfo — the symbolic name (used in
suppression comments and output) paired with the rule-specific
problem description (used to build violation messages). One
declaration per rule. No separate lookup table to drift out of sync
with the enum itself.
"""

from enum import Enum
from typing import NamedTuple


class RuleInfo(NamedTuple):
    """The symbolic name of a rule and problem description."""

    symbolic_name: str
    problem: str


class Rule(Enum):
    """All pyrigor rules implemented or planned."""

    PYR401 = RuleInfo(
        symbolic_name="namedtuple-returns",
        problem="returns a bare multi-value tuple; use a NamedTuple instead",
    )
    PYR402 = RuleInfo(
        symbolic_name="keyword-only-arguments",
        problem="has positional parameters; all parameters should be keyword-only",
    )

    PYR405 = RuleInfo(
        symbolic_name="namedtuple-parameters",
        problem="has a parameter typed as a bare multi-value tuple; use a NamedTuple instead",
    )

    @property
    def symbolic_name(self) -> str:
        """The symbolic name of the rule, for suppression comments and output."""
        return self.value.symbolic_name

    @property
    def problem(self) -> str:
        """The rule-specific problem description, for violation messages."""
        return self.value.problem
