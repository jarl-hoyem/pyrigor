"""Tests for how PYR406 resolves a call when an if or match statement binds the name in the alternative arms.

Only an if statement and a match statement count as alternative paths. A call is flagged when any binding that can
reach it is a protected definition. A later binding replaces an earlier one only when it runs on every path to the call.
"""

import textwrap

import pytest

from pyrigor.checkers.pyr406_return_values_used import find_findings
from tests.checker_helpers import check_source

_INT = "def v() -> int:\n    return 1\n"
_NONE = "def v() -> None:\n    return None\n"
_LAMBDA = "v = lambda: None\n"
_CALL = "v()\n"
_IN_MODULE_AND_FUNCTION = pytest.mark.parametrize("in_function", [False, True], ids=["module", "function"])


def _indent(*, code: str, levels: int = 1) -> str:
    """Indent a block of code by whole levels."""
    return textwrap.indent(code, "    " * levels)


def _if(*, body: str, or_else: str = "", after: str = _CALL) -> str:
    """Build an if statement with an else arm when one is given, followed by the code after it."""
    source = f"if condition:\n{_indent(code=body)}"
    if or_else:
        source += f"else:\n{_indent(code=or_else)}"
    return source + after


def _match(*, first: str, second: str, after: str = _CALL) -> str:
    """Build a match statement with two cases, followed by the code after it."""
    return (
        f"match command:\n    case 1:\n{_indent(code=first, levels=2)}"
        f"    case _:\n{_indent(code=second, levels=2)}{after}"
    )


def _count(*, source: str, in_function: bool) -> int:
    """Count the PYR406 findings in a source, written at module level or inside a function."""
    if in_function:
        source = f"def outer(condition: bool) -> None:\n{_indent(code=source)}"
    return len(check_source(source=source, checker=find_findings))


@_IN_MODULE_AND_FUNCTION
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(_if(body=_INT, or_else=_NONE), 1, id="the-reported-case-protected-then-unprotected"),
        pytest.param(_if(body=_NONE, or_else=_INT), 1, id="the-arms-swapped"),
        pytest.param(_if(body=_NONE, or_else=_NONE), 0, id="no-arm-is-protected"),
        pytest.param(_if(body=_INT, or_else=_INT), 1, id="every-arm-is-protected"),
        pytest.param(
            f"if condition:\n{_indent(code=_NONE)}elif other:\n{_indent(code=_INT)}else:\n{_indent(code=_NONE)}{_CALL}",
            1,
            id="a-protected-definition-in-an-elif-arm",
        ),
        pytest.param(
            _if(body="async def v() -> int:\n    return 1\n", or_else=_NONE),
            1,
            id="an-async-definition-in-one-arm",
        ),
        pytest.param(_NONE + _if(body=_INT), 1, id="a-one-armed-if-with-a-protected-definition"),
        pytest.param(_INT + _if(body=_NONE), 1, id="a-one-armed-if-does-not-hide-the-earlier-protected-definition"),
        pytest.param(_INT + _if(body=_LAMBDA), 1, id="a-lambda-in-a-branch-does-not-hide-the-earlier-definition"),
        pytest.param(_LAMBDA + _if(body=_INT), 1, id="a-definition-in-a-branch-after-a-lambda"),
        pytest.param(_if(body=_LAMBDA, or_else=_LAMBDA), 0, id="a-lambda-in-every-arm"),
    ],
)
def test_a_name_bound_in_alternative_arms(*, source: str, expected: int, in_function: bool) -> None:
    """The call is flagged when any arm can leave a protected definition behind."""
    assert _count(source=source, in_function=in_function) == expected


@_IN_MODULE_AND_FUNCTION
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(_if(body=_INT, or_else=_INT, after=_NONE + _CALL), 0, id="a-later-definition-replaces-both-arms"),
        pytest.param(_if(body=_NONE, or_else=_NONE, after=_INT + _CALL), 1, id="a-later-protected-definition"),
        pytest.param(_INT + _if(body=_NONE, after=_NONE + _CALL), 0, id="a-later-definition-after-the-branch"),
        pytest.param(_if(body=_INT + _NONE, or_else=_NONE), 0, id="a-later-definition-in-the-same-arm"),
        pytest.param(_if(body=_INT + _NONE, or_else=_INT), 1, id="the-other-arm-still-leaves-a-protected-definition"),
        pytest.param(_INT + "if (v := other()):\n    pass\n" + _CALL, 0, id="an-assignment-expression-in-the-test"),
    ],
)
def test_a_later_binding_replaces_an_earlier_one_only_when_it_runs_on_every_path(
    *, source: str, expected: int, in_function: bool
) -> None:
    """A binding inside a branch leaves the bindings before the branch reachable, and one after the branch does not."""
    assert _count(source=source, in_function=in_function) == expected


@_IN_MODULE_AND_FUNCTION
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(_if(body=_INT + _CALL, or_else=_NONE, after=""), 1, id="in-the-protected-arm"),
        pytest.param(_if(body=_INT, or_else=_NONE + _CALL, after=""), 0, id="in-the-unprotected-arm"),
        pytest.param(_if(body=_NONE + _CALL, or_else=_INT, after=""), 0, id="in-the-unprotected-first-arm"),
        pytest.param(_if(body=_NONE, or_else=_INT + _CALL, after=""), 1, id="in-the-protected-else-arm"),
        pytest.param(_INT + _if(body=_NONE + _CALL, after=""), 0, id="in-an-arm-that-replaces-the-earlier-definition"),
        pytest.param(_NONE + _if(body=_INT + _CALL, after=""), 1, id="in-an-arm-that-defines-it"),
        pytest.param(
            f"if condition:\n    v()\nelse:\n{_indent(code=_INT)}", 0, id="the-only-definition-is-in-the-other-arm"
        ),
    ],
)
def test_a_call_inside_an_arm_ignores_the_other_arm(*, source: str, expected: int, in_function: bool) -> None:
    """A definition in the other arm never runs before the call, so it cannot decide it."""
    assert _count(source=source, in_function=in_function) == expected


@_IN_MODULE_AND_FUNCTION
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            f"if outer:\n{_indent(code=_if(body=_INT, or_else=_NONE, after=''))}else:\n{_indent(code=_NONE)}{_CALL}",
            1,
            id="nested-branches-leave-one-protected-path",
        ),
        pytest.param(
            f"if outer:\n{_indent(code=_if(body=_INT, or_else=_NONE + _CALL, after=''))}else:\n{_indent(code=_INT)}",
            0,
            id="a-call-in-the-inner-else-arm-ignores-the-outer-else-arm",
        ),
        pytest.param(
            f"if outer:\n{_indent(code=_if(body=_NONE, or_else=_NONE, after=''))}else:\n{_indent(code=_INT)}{_CALL}",
            1,
            id="the-outer-else-arm-is-protected",
        ),
    ],
)
def test_nested_branches(*, source: str, expected: int, in_function: bool) -> None:
    """Each branching statement is judged on its own, however deep."""
    assert _count(source=source, in_function=in_function) == expected


@_IN_MODULE_AND_FUNCTION
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(_match(first=_INT, second=_NONE), 1, id="the-first-case-is-protected"),
        pytest.param(_match(first=_NONE, second=_INT), 1, id="the-second-case-is-protected"),
        pytest.param(_match(first=_NONE, second=_NONE), 0, id="no-case-is-protected"),
        pytest.param(_match(first=_INT, second=_NONE + _CALL, after=""), 0, id="a-call-in-the-unprotected-case"),
        pytest.param(_match(first=_INT + _CALL, second=_NONE, after=""), 1, id="a-call-in-the-protected-case"),
        pytest.param(_match(first=_INT, second=_INT, after=_NONE + _CALL), 0, id="a-later-definition-after-the-match"),
        pytest.param(
            _INT + "match (v := other()):\n    case _:\n        pass\n" + _CALL,
            0,
            id="an-assignment-expression-in-the-subject",
        ),
        pytest.param(
            _INT + "match command:\n    case 1:\n        pass\n    case v:\n        pass\n" + _CALL,
            1,
            id="a-capture-pattern-counts-as-conditional",
        ),
    ],
)
def test_a_name_bound_in_match_cases(*, source: str, expected: int, in_function: bool) -> None:
    """A match statement is judged like an if statement, with one arm for each case."""
    assert _count(source=source, in_function=in_function) == expected


@_IN_MODULE_AND_FUNCTION
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(f"for item in items:\n{_indent(code=_INT)}{_NONE}{_CALL}", 0, id="a-for-loop"),
        pytest.param(f"while condition:\n{_indent(code=_INT)}{_NONE}{_CALL}", 0, id="a-while-loop"),
        pytest.param(
            f"try:\n{_indent(code=_INT)}except ValueError:\n{_indent(code=_NONE)}{_CALL}",
            0,
            id="a-try-statement",
        ),
        pytest.param(
            f"with manager:\n{_indent(code=_INT)}with manager:\n{_indent(code=_NONE)}{_CALL}",
            0,
            id="a-with-statement",
        ),
    ],
)
def test_other_compound_statements_stay_sequential(*, source: str, expected: int, in_function: bool) -> None:
    """Loops, try statements and with statements are not alternative paths, so the latest definition decides."""
    assert _count(source=source, in_function=in_function) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "def outer(condition: bool) -> None:\n"
            f"{_indent(code=_if(body=_INT, or_else=_NONE, after=''))}"
            "    def inner() -> None:\n        v()\n",
            1,
            id="a-nested-function-sees-every-arm-of-the-enclosing-function",
        ),
        pytest.param(
            "def outer(condition: bool) -> None:\n"
            f"{_indent(code=_if(body=_INT, or_else=_NONE, after=_NONE))}"
            "    def inner() -> None:\n        v()\n",
            0,
            id="a-nested-function-sees-a-later-unconditional-definition-only",
        ),
        pytest.param(
            f"{_if(body=_INT, or_else=_NONE, after='')}\n\ndef user() -> None:\n    v()\n",
            1,
            id="another-function-sees-every-arm-of-the-module",
        ),
        pytest.param(
            f"{_if(body=_INT, or_else=_NONE, after=_NONE)}\n\ndef user() -> None:\n    v()\n",
            0,
            id="another-function-sees-a-later-unconditional-module-definition-only",
        ),
        pytest.param(
            f"if condition:\n{_indent(code=_INT)}else:\n    def user() -> None:\n        v()\n",
            1,
            id="a-function-in-the-other-arm-still-sees-the-definition",
        ),
        pytest.param(
            f"if condition:\n    def outer(v) -> None:\n        v()\n{_INT}",
            0,
            id="a-parameter-in-a-function-inside-a-branch-is-its-own-binding",
        ),
    ],
)
def test_a_call_in_another_scope_sees_every_arm(*, source: str, expected: int) -> None:
    """A call in another scope is not inside any arm, so only an unconditional later binding replaces an earlier one."""
    assert len(check_source(source=source, checker=find_findings)) == expected
