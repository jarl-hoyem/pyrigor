"""Tests for the PYR403 checker (keyword-only single argument)."""
# test assertions compare against expected literal values by design,
# not a magic-value problem

# noinspection PyProtectedMember
from pyrigor.checkers.pyr403_keyword_only_single_argument import find_findings
from pyrigor.rules import Rule
from tests.checker_helpers import check_source


def test_flags_single_positional_parameter() -> None:
    """A function with exactly one positional parameter should be flagged."""
    source = """
def load_config(path):
    ...
"""
    findings = check_source(source=source, checker=find_findings)

    assert len(findings) == 1
    assert findings[0].message.startswith("Function 'load_config' ")
    assert findings[0].code is Rule.PYR403


def test_no_finding_for_already_keyword_only_single_parameter() -> None:
    """A single parameter that is already keyword-only should not be flagged."""
    source = """
def load_config(*, path):
    ...
"""
    findings = check_source(source=source, checker=find_findings)

    assert not findings


def test_no_finding_for_two_parameters() -> None:
    """A function with two parameters is not PYR403's territory. It belongs to PYR402."""
    source = """
def compute(a, b):
    ...
"""
    findings = check_source(source=source, checker=find_findings)

    assert not findings


def test_flags_method_with_self_and_one_positional_parameter() -> None:
    """A method with self plus one real positional parameter should be flagged, on the real parameter."""
    source = """
class Loader:
    def load(self, path):
        ...
"""
    findings = check_source(source=source, checker=find_findings)

    assert len(findings) == 1
    assert findings[0].message.startswith("Function 'load' ")


def test_no_finding_for_zero_parameters() -> None:
    """A function with no parameters at all should not be flagged."""
    source = """
def run() -> None:
    ...
"""
    findings = check_source(source=source, checker=find_findings)

    assert not findings


def test_flags_async_function_with_single_positional_parameter() -> None:
    """An async function with exactly one positional parameter should be flagged."""
    source = """
async def load_config(path):
    ...
"""
    findings = check_source(source=source, checker=find_findings)

    assert len(findings) == 1
    assert findings[0].message.startswith("Function 'load_config' ")
