"""Registry of all pyrigor rules.

Each Rule member's value is a RuleInfo — the symbolic name (used in
suppression comments and output) paired with the rule-specific
problem description (used to build violation messages) and its
severity. One declaration per rule. No separate lookup table to
drift out of sync with the enum itself.
"""

from enum import Enum
from typing import NamedTuple


class Severity(Enum):
    """A rule's severity, matching the Language Server Protocol's own DiagnosticSeverity naming.

    Graded by consequence severity if the underlying pattern's bug
    actually occurs, not by how likely that is. See DECISIONS.md for
    the full per-rule reasoning.
    """

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class RuleInfo(NamedTuple):
    """The symbolic name, problem description, and severity of a rule."""

    symbolic_name: str
    problem: str
    severity: Severity


class Rule(Enum):
    """All pyrigor rules implemented or planned."""

    PYR301 = RuleInfo(
        symbolic_name="namedtuple-values",
        problem="is annotated as a bare multi-value tuple; use a NamedTuple instead",
        severity=Severity.WARNING,
    )

    PYR401 = RuleInfo(
        symbolic_name="namedtuple-returns",
        problem="returns a bare multi-value tuple; use a NamedTuple instead",
        severity=Severity.WARNING,
    )
    PYR402 = RuleInfo(
        symbolic_name="keyword-only-arguments",
        problem="has positional parameters; all parameters should be keyword-only",
        severity=Severity.WARNING,
    )

    PYR403 = RuleInfo(
        symbolic_name="keyword-only-single-argument",
        problem="has a single positional parameter; it should be keyword-only",
        severity=Severity.WARNING,
    )

    PYR405 = RuleInfo(
        symbolic_name="namedtuple-parameters",
        problem="has a parameter typed as a bare multi-value tuple; use a NamedTuple instead",
        severity=Severity.WARNING,
    )

    PYR406 = RuleInfo(
        symbolic_name="return-values-used",
        problem="is called and its return value is discarded; use the result",
        severity=Severity.ERROR,
    )

    @property
    def symbolic_name(self) -> str:
        """The symbolic name of the rule, for suppression comments and output."""
        return self.value.symbolic_name

    @property
    def problem(self) -> str:
        """The rule-specific problem description, for violation messages."""
        return self.value.problem

    @property
    def severity(self) -> Severity:
        """The rule's severity level, matching LSP's DiagnosticSeverity naming."""
        return self.value.severity
