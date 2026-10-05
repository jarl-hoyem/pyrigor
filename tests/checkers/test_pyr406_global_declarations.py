"""Tests for how PYR406 resolves a call to a name that a function declares global.

Python never makes such a name local to the declaring function. A function that declares it global and assigns to it
rebinds the module's name, and a function nested inside it reaches the module too, not the declaring function.
Inside the declaring function itself, the order of its own stores decides what a call reaches.
"""

import pytest

from pyrigor.checkers.pyr406_return_values_used import find_findings
from tests.checker_helpers import check_source

_PROTECTED_DEF = """
def calculate() -> int:
    return 42

"""
_PROTECTED_DEF_AT_END = """

def calculate() -> int:
    return 42
"""
_UNPROTECTED_DEF = """
def calculate() -> None:
    return None

"""


def _count(*, source: str) -> int:
    """Count the PYR406 findings in a source."""
    return len(check_source(source=source, checker=find_findings))


# noinspection IncorrectFormatting
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            _PROTECTED_DEF + "def wrapper():\n    global calculate\n    calculate = lambda: None\n    calculate()\n",
            0,
            id="the-call-follows-the-rebinding-in-the-same-function",
        ),
        pytest.param(
            "def wrapper():\n    global calculate\n    calculate = lambda: None\n    calculate()\n"
            + _PROTECTED_DEF_AT_END,
            0,
            id="the-same-when-the-definition-comes-after-the-function",
        ),
        pytest.param(
            _PROTECTED_DEF + "def wrapper():\n    global calculate\n    calculate()\n    calculate = lambda: None\n",
            1,
            id="the-call-precedes-the-rebinding-so-it-reaches-the-module-definition",
        ),
        pytest.param(
            _PROTECTED_DEF + "def wrapper():\n    global calculate\n    calculate()\n",
            1,
            id="the-name-is-only-called",
        ),
        pytest.param(
            _PROTECTED_DEF + "def wrapper():\n    global calculate\n    calculate = lambda: None; calculate()\n",
            0,
            id="the-store-and-the-call-share-a-line",
        ),
        pytest.param(
            _PROTECTED_DEF + "def wrapper():\n    calculate = lambda: None\n    calculate()\n",
            0,
            id="without-a-global-declaration-the-assignment-is-local",
        ),
        pytest.param(
            _PROTECTED_DEF
            + "def wrapper():\n    global calculate\n    def calculate() -> int:\n        return 1\n    calculate()\n",
            1,
            id="a-definition-in-the-function-decides-the-call-after-it",
        ),
        pytest.param(
            _PROTECTED_DEF + "def wrapper():\n    global calculate\n    def calculate() -> None:\n"
            "        return None\n    calculate()\n",
            0,
            id="an-unprotected-definition-in-the-function-decides-the-call-after-it",
        ),
        pytest.param(
            _UNPROTECTED_DEF
            + "def wrapper():\n    global calculate\n    calculate()\n    def calculate() -> int:\n        return 1\n",
            0,
            id="a-later-definition-in-the-function-does-not-decide-an-earlier-call",
        ),
        pytest.param(
            _PROTECTED_DEF
            + "def wrapper():\n    global calculate\n    calculate = lambda: None\n    def calculate() -> int:\n"
            "        return 1\n    calculate()\n",
            1,
            id="the-latest-store-before-the-call-decides",
        ),
        pytest.param(
            _PROTECTED_DEF + "def wrapper():\n    global calculate\n    def calculate() -> int:\n        return 1\n"
            "    calculate = lambda: None\n    calculate()\n",
            0,
            id="the-latest-store-before-the-call-decides-in-the-other-order",
        ),
        pytest.param(
            _PROTECTED_DEF
            + "def wrapper():\n    global other, calculate\n    calculate = lambda: None\n    calculate()\n",
            0,
            id="the-declaration-names-several-names",
        ),
        pytest.param(
            _PROTECTED_DEF
            + "def wrapper():\n    global calculate\n    from helpers import calculate\n    calculate()\n",
            0,
            id="an-import-rebinds-the-global-name",
        ),
        pytest.param(
            _PROTECTED_DEF + "async def wrapper():\n    global calculate\n    calculate()\n",
            1,
            id="an-async-function-declares-it",
        ),
        pytest.param(
            "def wrapper():\n    global calculate\n    helper = lambda: None\n    helper()\n\n\n"
            "def helper() -> int:\n    return 1\n",
            0,
            id="another-name-in-the-same-function-stays-local",
        ),
    ],
)
def test_a_call_in_the_function_that_declares_the_name_global(*, source: str, expected: int) -> None:
    """The order of the function's own stores decides, and a store after the call has not happened yet."""
    assert _count(source=source) == expected


# noinspection IncorrectFormatting
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            _PROTECTED_DEF + "def wrapper():\n    global calculate\n    calculate = lambda: None\n"
            "    def inner():\n        calculate()\n",
            0,
            id="a-nested-function-reaches-the-module-and-the-latest-binding-is-the-store",
        ),
        pytest.param(
            "def wrapper():\n    global calculate\n    calculate = lambda: None\n"
            "    def inner():\n        calculate()\n" + _PROTECTED_DEF_AT_END,
            1,
            id="a-nested-function-skips-the-declaring-function-so-the-later-definition-decides",
        ),
        pytest.param(
            "def setup():\n    global compute\n    def compute() -> int:\n        return 1\n\n\n"
            "def user():\n    compute()\n",
            1,
            id="a-name-defined-only-through-a-global-declaration-is-resolved",
        ),
        pytest.param(
            _UNPROTECTED_DEF
            + "def wrapper():\n    global calculate\n    def calculate() -> int:\n        return 1\n\n\ncalculate()\n",
            1,
            id="a-module-level-call-sees-the-latest-binding-whichever-scope-holds-it",
        ),
        pytest.param(
            _PROTECTED_DEF + "def wrapper():\n    global calculate\n    calculate = lambda: None\n\n\ncalculate()\n",
            0,
            id="a-module-level-call-sees-the-latest-binding-even-from-a-function",
        ),
        pytest.param(
            _PROTECTED_DEF
            + "def wrapper():\n    global calculate\n    calculate = lambda: None\n\n\ndef user():\n    calculate()\n",
            0,
            id="another-function-reaches-the-module-and-the-latest-binding-is-the-store",
        ),
    ],
)
def test_a_call_outside_the_function_that_declares_the_name_global(*, source: str, expected: int) -> None:
    """Every other scope reaches the module, whose latest binding in source order decides, as for any module name."""
    assert _count(source=source) == expected


# noinspection IncorrectFormatting
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            _PROTECTED_DEF + "global calculate\n\ncalculate()\n\n\ndef calculate() -> None:\n    return None\n",
            0,
            id="a-global-statement-at-module-level-changes-nothing",
        ),
        pytest.param(
            _PROTECTED_DEF + "def wrapper():\n    class Inner:\n        global calculate\n"
            "    calculate()\n    calculate = lambda: None\n",
            0,
            id="a-global-statement-in-a-class-body-does-not-declare-it-for-the-function",
        ),
    ],
)
def test_a_global_statement_that_declares_nothing_for_the_function(*, source: str, expected: int) -> None:
    """A global statement at module level has no effect, and one in a class body belongs to the class."""
    assert _count(source=source) == expected
