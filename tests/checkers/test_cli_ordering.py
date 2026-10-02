"""Tests for pyrigor's deterministic output ordering (#239)."""
# test assertions compare against expected literal values by design, not a magic-value problem
# pylint: disable=magic-value-comparison

import json
from os.path import relpath
from pathlib import Path

import pytest

import pyrigor.checkers.cli as cli_module
from pyrigor.checkers import CHECKERS

# noinspection PyProtectedMember
from pyrigor.checkers.cli import (
    _check_file,  # pyright: ignore[reportPrivateUsage]
    _file_sort_key,  # pyright: ignore[reportPrivateUsage]
    _files_in_directory,  # pyright: ignore[reportPrivateUsage]
    _finding_sort_key,  # pyright: ignore[reportPrivateUsage]
    main,
)
from pyrigor.rules import Rule
from pyrigor.suppression import SuppressionResult
from tests.checker_helpers import finding_at


def _without_elapsed_time(*, output: str) -> str:
    """Strip the human summary's elapsed-time line, which legitimately varies between runs."""
    return "\n".join(line for line in output.splitlines() if not line.startswith("Checked "))


def test_finding_sort_key_reads_position_fields_by_name() -> None:
    """The sort key exposes line, column and end position by name, not only by tuple position."""
    finding = finding_at(line=3, end_line=4, column=5, end_column=6, rule=Rule.PYR402)

    key = _finding_sort_key(finding=finding)

    assert key.line == 3
    assert key.column == 5
    assert key.end_line == 4
    assert key.end_column == 6


def test_finding_sort_key_reads_rule_code_field_by_name() -> None:
    """The sort key exposes the rule's code by name, not only by tuple position."""
    finding = finding_at(line=1, end_line=1, column=1, end_column=1, rule=Rule.PYR402)

    key = _finding_sort_key(finding=finding)

    assert key.rule_code == "PYR402"


def test_finding_sort_key_orders_by_line_then_column() -> None:
    """Findings at different positions sort by line first, then column."""
    later = finding_at(line=5, end_line=5, column=1, end_column=2, rule=Rule.PYR402)
    earlier_same_line_later_column = finding_at(line=2, end_line=2, column=9, end_column=10, rule=Rule.PYR402)
    earliest = finding_at(line=2, end_line=2, column=1, end_column=2, rule=Rule.PYR402)

    ordered = sorted([later, earlier_same_line_later_column, earliest], key=lambda v: _finding_sort_key(finding=v))

    assert ordered == [earliest, earlier_same_line_later_column, later]


def test_finding_sort_key_breaks_a_tied_start_by_end_position() -> None:
    """Two findings sharing a start position order by end position next."""
    shorter = finding_at(line=1, end_line=1, column=1, end_column=3, rule=Rule.PYR402)
    longer = finding_at(line=1, end_line=1, column=1, end_column=10, rule=Rule.PYR401)

    ordered = sorted([longer, shorter], key=lambda v: _finding_sort_key(finding=v))

    assert ordered == [shorter, longer]


def test_finding_sort_key_breaks_a_tied_position_by_rule_code() -> None:
    """Two findings sharing the same start and end position order by rule code last."""
    pyr402_finding = finding_at(line=1, end_line=1, column=1, end_column=10, rule=Rule.PYR402)
    pyr401_finding = finding_at(line=1, end_line=1, column=1, end_column=10, rule=Rule.PYR401)

    ordered = sorted([pyr402_finding, pyr401_finding], key=lambda v: _finding_sort_key(finding=v))

    assert ordered == [pyr401_finding, pyr402_finding]


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


def test_check_file_orders_suppressed_findings_by_position(*, tmp_path: Path) -> None:
    """Suppressed findings from different rules come back ordered by position, not checker registration order.

    Exercise the partition before it is serialised into JSON.
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

    assert [next(span for span in finding.spans if span.is_primary).line_start for finding in result.suppressed] == [
        1,
        6,
    ]


# pyrigor 402 # pytest fixture injection, not a real finding
def test_check_file_sorts_kept_and_suppressed_by_the_explicit_position_key(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kept and suppressed both sorts by the explicit (line, column, end_line, end_column, rule) key.

    These findings share a line but have different columns and end lines. The smaller column must win,
    regardless of the end line or the order returned by the suppression filter.
    """
    source_file = tmp_path / "source.py"
    source_file.write_text("x = 1\n")
    small_column_large_end_line = finding_at(line=1, end_line=8, column=3, end_column=4, rule=Rule.PYR402)
    large_column_small_end_line = finding_at(line=1, end_line=2, column=10, end_column=11, rule=Rule.PYR401)
    fixed_result = SuppressionResult(
        kept=[large_column_small_end_line, small_column_large_end_line],
        suppressed=[large_column_small_end_line, small_column_large_end_line],
    )

    def fake_filter_suppressed(**_ignored: object) -> SuppressionResult:
        """Return the fixed result regardless of the real arguments, which this test does not need."""
        return fixed_result

    monkeypatch.setattr(cli_module, "filter_suppressed", fake_filter_suppressed)

    result = _check_file(path=str(source_file), checkers=CHECKERS)

    assert result.kept == [small_column_large_end_line, large_column_small_end_line]
    assert result.suppressed == [small_column_large_end_line, large_column_small_end_line]


# pyrigor 402 # pytest fixture injection, not a real finding
def test_main_json_findings_are_ordered_by_file_then_position(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """JSON findings come out ordered by relative file name, then by position within a file.

    Complements the enumeration-order-independence test above, which only checks that two runs agree with each
    other, not that the agreed-upon order is the expected one.
    """
    (tmp_path / "b.py").write_text("def two(x, y):\n    ...\n")
    (tmp_path / "a.py").write_text(
        "def apply_correction(weight, bias):\n    ...\n\n\n\ndef returns_pair() -> tuple[int, int]:\n    ...\n"
    )

    main(paths=[str(tmp_path)], output_format="json")

    document = json.loads(capsys.readouterr().out)
    locations = [(d["spans"][0]["file_name"], d["spans"][0]["line_start"]) for d in document["findings"]]
    assert locations == [
        (Path(relpath(tmp_path / "a.py")).as_posix(), 1),
        (Path(relpath(tmp_path / "a.py")).as_posix(), 6),
        (Path(relpath(tmp_path / "b.py")).as_posix(), 1),
    ]


# pyrigor 402 # pytest fixture injection, not a real finding
def test_main_orders_findings_within_a_file_by_position_not_checker_registration_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A file with two rules' findings prints them by line, even though PYR401 is checked before PYR402."""
    source_file = tmp_path / "bad.py"
    source_file.write_text(
        "def apply_correction(weight, bias):\n    ...\n\n\n\ndef returns_pair() -> tuple[int, int]:\n    ...\n"
    )

    main(paths=[str(source_file)])

    diagnostic_lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith(str(source_file))]
    assert diagnostic_lines[0].startswith(f"{source_file}:1:")
    assert diagnostic_lines[1].startswith(f"{source_file}:6:")


# pyrigor 402 # pytest fixture injection, not a real finding
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


# pyrigor 402 # pytest fixture injection, not a real finding
def test_main_orders_files_by_normalized_key_not_native_separator_comparison(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A nested file sorts before an uppercase-prefixed sibling, which only holds under forward-slash normalisation.

    Raw path comparison ranks these the other way: 'A' (0x41) sorts before a backslash (0x5C),
    but a forward slash (0x2F) sorts before 'A'. Proves main() uses the normalised key, not a plain string sort.
    """
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "Z.py").write_text("def one(x, y):\n    ...\n")
    (tmp_path / "aA.py").write_text("def two(x, y):\n    ...\n")

    main(paths=[str(tmp_path)])

    out = capsys.readouterr().out
    nested_position = out.index(str(tmp_path / "a" / "Z.py"))
    sibling_position = out.index(str(tmp_path / "aA.py"))
    assert nested_position < sibling_position


# pyrigor 402 # pytest fixture injection, not a real finding
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


# pyrigor 402 # pytest fixture injection, not a real finding
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
    assert [error["file_name"] for error in document["errors"]] == [
        Path(relpath(path)).as_posix() for path in (a_unparseable, z_unreadable)
    ]
