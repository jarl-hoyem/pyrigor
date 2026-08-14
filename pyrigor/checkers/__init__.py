"""AST-based checkers for pyrigor's guidelines."""

import ast
from typing import Protocol

from pyrigor.checkers.pyr301_namedtuple_values import find_violations as _pyr301
from pyrigor.checkers.pyr401_namedtuple_returns import find_violations as _pyr401
from pyrigor.checkers.pyr402_keyword_only_arguments import find_violations as _pyr402
from pyrigor.checkers.pyr403_keyword_only_single_argument import find_violations as _pyr403
from pyrigor.checkers.pyr405_namedtuple_parameters import find_violations as _pyr405
from pyrigor.violations import Violation


class _CheckerFun(Protocol):  # pylint: disable=too-few-public-methods
    """A checker's find_violations function, called by a keyword."""

    def __call__(self, *, tree: ast.Module) -> list[Violation]: ...


CHECKERS: tuple[_CheckerFun, ...] = (_pyr301, _pyr401, _pyr402, _pyr403, _pyr405)

__all__ = ["CHECKERS"]
