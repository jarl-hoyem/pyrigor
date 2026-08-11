"""AST-based checkers for pyrigor's guidelines."""

# pyrigor/checkers/__init__.py
from pyrigor.checkers.pyr003_keyword_only_arguments import find_violations as find_pyr003_violations

__all__ = ["find_pyr003_violations"]
