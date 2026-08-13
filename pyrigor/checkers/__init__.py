"""AST-based checkers for pyrigor's guidelines."""

from collections.abc import Callable

from pyrigor.checkers.pyr401_namedtuple_returns import find_violations as _pyr401
from pyrigor.checkers.pyr402_keyword_only_arguments import find_violations as _pyr402
from pyrigor.violations import Violation

CHECKERS: tuple[Callable[[str], list[Violation]], ...] = (_pyr401, _pyr402)

__all__ = ["CHECKERS"]
