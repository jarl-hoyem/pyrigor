"""AST-based checkers for pyrigor's guidelines."""

import ast
from typing import NamedTuple, Protocol

from pyrigor.checkers.pyr301_namedtuple_values import find_violations as _pyr301
from pyrigor.checkers.pyr401_namedtuple_returns import find_violations as _pyr401
from pyrigor.checkers.pyr402_keyword_only_arguments import find_violations as _pyr402
from pyrigor.checkers.pyr403_keyword_only_single_argument import find_violations as _pyr403
from pyrigor.checkers.pyr405_namedtuple_parameters import find_violations as _pyr405
from pyrigor.rules import Rule
from pyrigor.violations import Violation


class _CheckerFun(Protocol):  # pylint: disable=too-few-public-methods
    """A checker's find_violations function, called by a keyword."""

    def __call__(self, *, tree: ast.Module) -> list[Violation]: ...


class RegisteredChecker(NamedTuple):
    """A checker explicitly paired with the rule it enforces.

    Explicit pairing avoids relying on CHECKERS and Rule sharing the
    same declaration order, which nothing previously enforced.
    """

    rule: Rule
    find_violations: _CheckerFun


CHECKERS: tuple[RegisteredChecker, ...] = (
    RegisteredChecker(rule=Rule.PYR301, find_violations=_pyr301),
    RegisteredChecker(rule=Rule.PYR401, find_violations=_pyr401),
    RegisteredChecker(rule=Rule.PYR402, find_violations=_pyr402),
    RegisteredChecker(rule=Rule.PYR403, find_violations=_pyr403),
    RegisteredChecker(rule=Rule.PYR405, find_violations=_pyr405),
)

__all__ = ["CHECKERS", "RegisteredChecker"]
