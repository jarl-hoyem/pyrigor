"""Tests for pyrigor's deterministic output ordering (#239)."""
# test assertions compare against expected literal values by design, not a magic-value problem
# pylint: disable=magic-value-comparison

import json
from pathlib import Path

import pytest

import pyrigor.checkers.cli as cli_module
from pyrigor.checkers import CHECKERS

# noinspection PyProtectedMember
from pyrigor.checkers.cli import (
    _check_file,  # pyright: ignore[reportPrivateUsage]
    _file_sort_key,  # pyright: ignore[reportPrivateUsage]
    _files_in_directory,  # pyright: ignore[reportPrivateUsage]
    _violation_sort_key,  # pyright: ignore[reportPrivateUsage]
    main,
)
from pyrigor.rules import Rule
from pyrigor.violations import Violation


def _without_elapsed_time(*, output: str) -> str:
    """Strip the human summary's elapsed-time line, which legitimately varies between runs."""
    return "\n".join(line for line in output.splitlines() if not line.startswith("Checked "))


def _violation(*, line: int, end_line: int, column: int, end_column: int, rule: Rule) -> Violation:
    """Build a minimal Violation for sort-key tests, only the position and rule vary."""
    return Violation(
        line=line,
        end_line=end_line,
        column=column,
        end_column=end_column,
        context_name="x",
        context_kind="Function",
        rule=rule,
    )


def test_violation_sort_key_reads_position_fields_by_name() -> None:
    """The sort key exposes line, column and end position by name, not only by tuple position."""
    violation = _violation(line=3, end_line=4, column=5, end_column=6, rule=Rule.PYR402)

    key = _violation_sort_key(violation=violation)

    assert key.line == 3
    assert key.column == 5
    assert key.end_line == 4
    assert key.end_column == 6


def test_violation_sort_key_reads_rule_code_field_by_name() -> None:
    """The sort key exposes the rule's code by name, not only by tuple position."""
    violation = _violation(line=1, end_line=1, column=1, end_column=1, rule=Rule.PYR402)

    key = _violation_sort_key(violation=violation)

    assert key.rule_code == "PYR402"


def test_violation_sort_key_orders_by_line_then_column() -> None:
    """Violations at different positions sort by line first, then column."""
    later = _violation(line=5, end_line=5, column=1, end_column=2, rule=Rule.PYR402)
    earlier_same_line_later_column = _violation(line=2, end_line=2, column=9, end_column=10, rule=Rule.PYR402)
    earliest = _violation(line=2, end_line=2, column=1, end_column=2, rule=Rule.PYR402)

    ordered = sorted([later, earlier_same_line_later_column, earliest], key=lambda v: _violation_sort_key(violation=v))

    assert ordered == [earliest, earlier_same_line_later_column, later]


def test_violation_sort_key_breaks_a_tied_start_by_end_position() -> None:
    """Two violations sharing a start position order by end position next."""
    shorter = _violation(line=1, end_line=1, column=1, end_column=3, rule=Rule.PYR402)
    longer = _violation(line=1, end_line=1, column=1, end_column=10, rule=Rule.PYR401)

    ordered = sorted([longer, shorter], key=lambda v: _violation_sort_key(violation=v))

    assert ordered == [shorter, longer]


def test_violation_sort_key_breaks_a_tied_position_by_rule_code() -> None:
    """Two violations sharing the same start and end position order by rule code last."""
    pyr402_violation = _violation(line=1, end_line=1, column=1, end_column=10, rule=Rule.PYR402)
    pyr401_violation = _violation(line=1, end_line=1, column=1, end_column=10, rule=Rule.PYR401)

    ordered = sorted([pyr402_violation, pyr401_violation], key=lambda v: _violation_sort_key(violation=v))

    assert ordered == [pyr401_violation, pyr402_violation]


def test_file_sort_key_normalizes_windows_separators_to_forward_slashes() -> None:
    """A path given with backslashes sorts identically to its forward-slash form."""
    assert _file_sort_key(path="a\\b.py") == _file_sort_key(path="a/b.py")


def test_file_sort_key_orders_nested_paths_and_case_by_code_point() -> None:
    """Case and nested-directory paths sort by Unicode code point: 'B' < 'a', and '.' < '/' < '_'."""
    paths = ["a_b.py", "a/b.py", "B.py", "a.py"]

    ordered = sorted(paths, key=lambda path: _file_sort_key(path=path))

    assert ordered == ["B.py", "a.py", "a/b.py", "a_b.py"]


def test_file_sort_key_orders_a_path_separator_before_any_letter() -> None:
    """A directory separator (code point 0x2F) sorts before any letter, so a/b/c.py sorts before a/bb.py."""
    paths = ["a/bb.py", "a/b/c.py"]

    ordered = sorted(paths, key=lambda path: _file_sort_key(path=path))

    assert ordered == ["a/b/c.py", "a/bb.py"]


def test_check_file_orders_suppressed_violations_by_position(*, tmp_path: Path) -> None:
    """Suppressed violations from different rules come back ordered by position, not checker registration order.

    No current output format prints suppressed violations individually (only their counts), so this exercises
    _check_file directly rather than through main().
    """
    source_file = tmp_path / "bad.py"
    source_file.write_text(
        "def apply_correction(weight, bias):  # pyrigor 402 # reason\n"
        "    ...\n"
        "\n"
        "\n"
        "\n"
        "def returns_pair() -> tuple[int, int]:  # pyrigor 401 # reason\n"
        "    ...\n"
    )

    result = _check_file(path=str(source_file), checkers=CHECKERS)

    assert [violation.line for violation in result.suppressed] == [1, 6]


# pyrigor 402 # pytest fixture injection, not a real violation
def test_main_json_diagnostics_are_ordered_by_file_then_position(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """JSON diagnostics come out ordered by file, then by position within a file, in absolute terms.

    Complements the enumeration-order-independence test above, which only checks that two runs agree with each
    other, not that the agreed-upon order is the expected one.
    """
    (tmp_path / "b.py").write_text("def two(x, y):\n    ...\n")
    (tmp_path / "a.py").write_text(
        "def apply_correction(weight, bias):\n    ...\n\n\n\ndef returns_pair() -> tuple[int, int]:\n    ...\n"
    )

    main(paths=[str(tmp_path)], output_format="json")

    document = json.loads(capsys.readouterr().out)
    locations = [(d["file"], d["location"]["start"]["line"]) for d in document["diagnostics"]]
    assert locations == [
        (str(tmp_path / "a.py"), 1),
        (str(tmp_path / "a.py"), 6),
        (str(tmp_path / "b.py"), 1),
    ]


# pyrigor 402 # pytest fixture injection, not a real violation
def test_main_orders_violations_within_a_file_by_position_not_checker_registration_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A file with two rules' violations prints them by line, even though PYR401 is checked before PYR402."""
    source_file = tmp_path / "bad.py"
    source_file.write_text(
        "def apply_correction(weight, bias):\n    ...\n\n\n\ndef returns_pair() -> tuple[int, int]:\n    ...\n"
    )

    main(paths=[str(source_file)])

    diagnostic_lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith(str(source_file))]
    assert diagnostic_lines[0].startswith(f"{source_file}:1:")
    assert diagnostic_lines[1].startswith(f"{source_file}:6:")


# pyrigor 402 # pytest fixture injection, not a real violation
def test_main_output_is_independent_of_path_argument_order(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Checking 'b.py a.py' and 'a.py b.py' produce identical output."""
    a_file = tmp_path / "a.py"
    b_file = tmp_path / "b.py"
    a_file.write_text("def one(x, y):\n    ...\n")
    b_file.write_text("def two(x, y):\n    ...\n")

    main(paths=[str(b_file), str(a_file)])
    reordered_output = _without_elapsed_time(output=capsys.readouterr().out)
    main(paths=[str(a_file), str(b_file)])
    natural_output = _without_elapsed_time(output=capsys.readouterr().out)

    assert reordered_output == natural_output


# pyrigor 402 # pytest fixture injection, not a real violation
def test_main_output_is_independent_of_directory_enumeration_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same files, discovered in reverse and shuffled order, produce identical human and JSON output."""
    (tmp_path / "a.py").write_text("def one(x, y):\n    ...\n")
    (tmp_path / "b.py").write_text("def two(x, y):\n    ...\n")
    (tmp_path / "c.py").write_text("def three(x, y):\n    ...\n")

    def reversed_enumeration(*, path: Path, excludes: tuple[Path, ...]) -> list[str]:
        """Return the real directory listing in reverse order."""
        return list(reversed(_files_in_directory(path=path, excludes=excludes)))

    def shuffled_enumeration(*, path: Path, excludes: tuple[Path, ...]) -> list[str]:
        """Return the real directory listing in a different, non-reversed order."""
        found = _files_in_directory(path=path, excludes=excludes)
        return [found[1], found[2], found[0]]

    # PyCharm widens this loop variable over a tuple of string literals to plain str rather than narrowing it to
    # 'Literal [ "human", "json"]'; mypy, pyright and ty all confirm main()'s output_format type is fine at both call
    # sites below.
    for output_format in ("human", "json"):
        monkeypatch.setattr(cli_module, "_files_in_directory", reversed_enumeration)
        # noinspection PyTypeChecker
        main(paths=[str(tmp_path)], output_format=output_format)
        reversed_output = _without_elapsed_time(output=capsys.readouterr().out)

        monkeypatch.setattr(cli_module, "_files_in_directory", shuffled_enumeration)
        # noinspection PyTypeChecker
        main(paths=[str(tmp_path)], output_format=output_format)
        shuffled_output = _without_elapsed_time(output=capsys.readouterr().out)

        assert reversed_output == shuffled_output, f"{output_format} output depended on enumeration order"


# pyrigor 402 # pytest fixture injection, not a real violation
def test_main_orders_operational_errors_by_file_in_stderr_and_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unreadable file and a parse-error file are reported in file order, both as warnings and as JSON errors."""
    z_unreadable = tmp_path / "z_unreadable.py"
    a_unparseable = tmp_path / "a_unparseable.py"
    z_unreadable.write_bytes(b"\xff\xfe\x00invalid")
    a_unparseable.write_text("def broken(:\n")

    main(paths=[str(z_unreadable), str(a_unparseable)])
    stderr = capsys.readouterr().err
    assert stderr.index(str(a_unparseable)) < stderr.index(str(z_unreadable))

    main(paths=[str(z_unreadable), str(a_unparseable)], output_format="json")
    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert [error["file"] for error in document["errors"]] == [str(a_unparseable), str(z_unreadable)]
