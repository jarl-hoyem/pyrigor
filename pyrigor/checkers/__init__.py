"""AST-based checkers for pyrigor's guidelines."""

from typing import Final, NamedTuple, Protocol

from pyrigor.checkers._shared import WalkedNodes, walk_once
from pyrigor.checkers.pyr301_namedtuple_values import find_findings as _pyr301
from pyrigor.checkers.pyr401_namedtuple_returns import find_findings as _pyr401
from pyrigor.checkers.pyr402_keyword_only_arguments import find_findings as _pyr402
from pyrigor.checkers.pyr403_keyword_only_single_argument import find_findings as _pyr403
from pyrigor.checkers.pyr405_namedtuple_parameters import find_findings as _pyr405
from pyrigor.checkers.pyr406_return_values_used import find_findings as _pyr406
from pyrigor.finding_builder import FindingContext
from pyrigor.findings import Finding
from pyrigor.rules import Rule


class _CheckerFun(Protocol):  # pylint: disable=too-few-public-methods
    """A checker's find_findings function, called by a keyword."""

    def __call__(self, *, nodes: WalkedNodes, context: FindingContext) -> list[Finding]:
        """Return findings found in the pre-walked nodes."""
        ...


# Intentional small NamedTuple structure matching shared checker records.
# noinspection DuplicatedCode
class RegisteredChecker(NamedTuple):
    """A checker explicitly paired with the rule it enforces.

    Explicit pairing avoids relying on CHECKERS and Rule sharing the
    same declaration order, which nothing previously enforced.
    """

    rule: Rule
    find_findings: _CheckerFun


# noinspection PyTypeChecker
CHECKERS: Final[tuple[RegisteredChecker, ...]] = (
    RegisteredChecker(rule=Rule.PYR301, find_findings=_pyr301),
    RegisteredChecker(rule=Rule.PYR401, find_findings=_pyr401),
    RegisteredChecker(rule=Rule.PYR402, find_findings=_pyr402),
    RegisteredChecker(rule=Rule.PYR403, find_findings=_pyr403),
    RegisteredChecker(rule=Rule.PYR405, find_findings=_pyr405),
    RegisteredChecker(rule=Rule.PYR406, find_findings=_pyr406),
)

__all__ = ["CHECKERS", "RegisteredChecker", "WalkedNodes", "walk_once"]
