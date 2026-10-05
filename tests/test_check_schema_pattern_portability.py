"""Test the cross-engine pattern check by running it the way the pre-commit hook does.

The check needs Node, which the mutation-testing image lacks, so the tests that run it for real are skipped there.
The failure paths that fake Node and the tests of the check's own arguments do not need it.
"""

import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path

import pytest

from tests.diagnostics_v2_support import REPOSITORY_ROOT
from tests.git_isolation import FixtureResult, run_command

_SCRIPT = REPOSITORY_ROOT / "scripts" / "check_schema_pattern_portability.py"
_BACKSLASH = chr(0x5C)
_WINDOWS_NAME = "nt"
_WINDOWS = os.name == _WINDOWS_NAME
_PATH_VARIABLE = "PATH"
_SUCCESS = "match alike in Python and Node"
_MORE_STRINGS = "/pattern: and "
_MAX_LISTED = 10  # written out, not imported from the script, so that changing the limit there fails the test
_PATTERN_PROPERTIES_REPORT = "/patternProperties/^a$: Python matches"
_USAGE = "usage: check_schema_pattern_portability.py [SCHEMA]"
_NODE_NOT_FOUND = "command not found: node"
_CORPUS_SIZE = re.compile(r" on (?P<count>\d+) strings")
_SETTING = re.compile(r"^ +(?P<key>\w+): (?P<value>.+)$", re.MULTILINE)
_PRE_COMMIT_CONFIG = REPOSITORY_ROOT / ".pre-commit-config.yaml"
_HOOK_ID = "schema-pattern-portability"
_HOOK_ENTRY = "uv run python scripts/check_schema_pattern_portability.py"
_FLAG_RUNS = 2  # Node is run without flags and with the Unicode flag, and each run lists its own disagreements
_NODE_UNREADABLE = "/pattern: Node cannot read"
_PYTHON_UNREADABLE = "/pattern: Python cannot read"
_BOTH_FLAGS = "with and without the u flag"
_U_FLAG_NODE = "Node with the u flag"
_PYTHON_ONLY = "Python matches"
_NODE_ONLY = "Node matches"
_NEEDS_NODE = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
_FAKE_NODE_NAME = "fake_node.py"
_FAILING_NODE = "import sys\nsys.stderr.write('boom')\nsys.exit(3)\n"
_SILLY_NODE = "print('this is not JSON')\n"


def _environment(*, path: str) -> dict[str, str]:
    """Copy the environment with the given PATH, replacing the variable whatever the case of its name."""
    kept = {name: value for name, value in os.environ.items() if name.upper() != _PATH_VARIABLE}
    return {**kept, _PATH_VARIABLE: path}


def _run(*, arguments: list[str], cwd: Path, path: str | None = None) -> FixtureResult:
    """Run the check with the given arguments, optionally with its own PATH."""
    environment = dict(os.environ) if path is None else _environment(path=path)
    return run_command(command=[sys.executable, str(_SCRIPT), *arguments], cwd=cwd, environment=environment)


def _schema(*, directory: Path, content: object) -> Path:
    """Write a schema file and return its path."""
    path = directory / "schema.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


def _install_fake_node(*, directory: Path, program: str) -> None:
    """Put a launcher called node on a directory, which runs a small Python program in place of Node."""
    (directory / _FAKE_NODE_NAME).write_text(program, encoding="utf-8")
    if _WINDOWS:
        launcher = directory / "node.cmd"
        launcher.write_text(f'@echo off\r\n"{sys.executable}" "{directory / _FAKE_NODE_NAME}" %*\r\n', encoding="utf-8")
    else:
        launcher = directory / "node"
        launcher.write_text(
            f'#!/bin/sh\nexec "{sys.executable}" "{directory / _FAKE_NODE_NAME}" "$@"\n', encoding="utf-8"
        )
        launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR)


@_NEEDS_NODE
def test_the_real_schema_reads_the_same_in_both_engines(*, tmp_path: Path) -> None:
    """Every pattern of the v2 schema matches alike in Python and in Node."""
    result = _run(arguments=[], cwd=tmp_path)
    assert (result.returncode, result.stderr) == (0, "")
    assert _SUCCESS in result.stdout
    assert _BOTH_FLAGS in result.stdout


@_NEEDS_NODE
@pytest.mark.parametrize(
    ("pattern", "reported", "named"),
    [
        pytest.param("^a$", [_PYTHON_ONLY], [f"'a{_BACKSLASH}n'"], id="dollar-before-a-final-line-feed"),
        pytest.param(
            "^a{3}$",
            [_PYTHON_ONLY],
            [f"'aaa{_BACKSLASH}n'"],
            id="dollar-before-a-final-line-feed-after-three-characters",
        ),
        pytest.param(f"^{_BACKSLASH}d$", [_PYTHON_ONLY], [f"'{_BACKSLASH}u0660'"], id="digit-beyond-ascii"),
        pytest.param(
            f"^{_BACKSLASH}s$",
            [_PYTHON_ONLY, _NODE_ONLY],
            [f"'{_BACKSLASH}x1c'", f"'{_BACKSLASH}ufeff'"],
            id="whitespace-set",
        ),
        pytest.param(
            "^[^a]$",
            [_PYTHON_ONLY],
            [f"'{_BACKSLASH}U0001d400'"],
            id="astral-letter-without-the-unicode-flag",
        ),
    ],
)
def test_a_pattern_the_engines_read_differently_fails_the_check(
    *, tmp_path: Path, pattern: str, reported: list[str], named: list[str]
) -> None:
    """A divergent pattern is named, with the engine that matches a string the other does not and that string."""
    result = _run(arguments=[str(_schema(directory=tmp_path, content={"pattern": pattern}))], cwd=tmp_path)
    assert result.returncode == 1
    assert all(f"/pattern: {engine}" in result.stdout for engine in reported)
    assert all(string in result.stdout for string in named)


def _corpus_size(*, directory: Path, pattern: str) -> int:
    """Run the check on a schema of one pattern and read how many strings it tried."""
    result = _run(arguments=[str(_schema(directory=directory, content={"pattern": pattern}))], cwd=directory)
    match = _CORPUS_SIZE.search(result.stdout)
    assert match is not None
    return int(match["count"])


@_NEEDS_NODE
@pytest.mark.parametrize(
    "named",
    [
        pytest.param(f"{_BACKSLASH}u3456", id="unicode-escape"),
        pytest.param(f"{_BACKSLASH}xe9", id="byte-escape"),
        pytest.param(chr(0x3456), id="literal-character"),
    ],
)
def test_a_code_point_a_pattern_names_adds_strings_to_the_corpus(*, tmp_path: Path, named: str) -> None:
    """The characters at and next to each code point that a pattern names are tried, so a new range is probed."""
    plain = _corpus_size(directory=tmp_path, pattern="[a-z]")
    assert _corpus_size(directory=tmp_path, pattern=f"[a-z{named}]") > plain


@_NEEDS_NODE
def test_only_the_first_disagreements_of_a_pattern_are_listed(*, tmp_path: Path) -> None:
    """A pattern with many disagreements is cut off with a count of the rest."""
    result = _run(arguments=[str(_schema(directory=tmp_path, content={"pattern": "."}))], cwd=tmp_path)
    assert result.returncode == 1
    assert _MORE_STRINGS in result.stdout
    assert result.stdout.count(f"/pattern: {_PYTHON_ONLY}") == _MAX_LISTED * _FLAG_RUNS


@_NEEDS_NODE
@pytest.mark.parametrize(
    "pattern",
    [
        pytest.param("[a-z]", id="unanchored-search"),
        pytest.param(f"^[a-z]+{_BACKSLASH}n*$", id="anchored-with-final-line-feeds"),
    ],
)
def test_a_pattern_both_engines_read_alike_passes(*, tmp_path: Path, pattern: str) -> None:
    """The forms the schema uses are accepted, including the one that ends in a run of line feeds."""
    result = _run(arguments=[str(_schema(directory=tmp_path, content={"pattern": pattern}))], cwd=tmp_path)
    assert (result.returncode, result.stderr) == (0, "")
    assert result.stdout.startswith("1 patterns match alike in Python and Node on ")


@_NEEDS_NODE
def test_a_pattern_under_pattern_properties_is_checked(*, tmp_path: Path) -> None:
    """The keys of patternProperties are patterns too."""
    schema = _schema(directory=tmp_path, content={"patternProperties": {"^a$": {}}})
    result = _run(arguments=[str(schema)], cwd=tmp_path)
    assert result.returncode == 1
    assert _PATTERN_PROPERTIES_REPORT in result.stdout


@_NEEDS_NODE
@pytest.mark.parametrize(
    ("pattern", "cannot_read"),
    [
        pytest.param("(a", ["Python", "Node"], id="unbalanced-group"),
        pytest.param("(?P<n>a)", ["Node"], id="python-named-group"),
        pytest.param("(?<n>a)", ["Python"], id="ecmascript-named-group"),
    ],
)
def test_a_pattern_an_engine_cannot_read_fails_the_check(
    *, tmp_path: Path, pattern: str, cannot_read: list[str]
) -> None:
    """A pattern that either engine rejects is named with the engine and its message."""
    result = _run(arguments=[str(_schema(directory=tmp_path, content={"pattern": pattern}))], cwd=tmp_path)
    assert result.returncode == 1
    for engine in ("Python", "Node"):
        assert (f"/pattern: {engine} cannot read the pattern" in result.stdout) is (engine in cannot_read)


@_NEEDS_NODE
@pytest.mark.parametrize(
    "pattern",
    [
        pytest.param(f"a{_BACKSLASH}-b", id="identity-escape"),
        pytest.param("a{", id="lone-brace"),
    ],
)
def test_a_pattern_only_the_u_flag_rejects_fails_the_check(*, tmp_path: Path, pattern: str) -> None:
    """Syntax that ECMAScript tolerates by default, and that a validator using the Unicode flag rejects, is named."""
    result = _run(arguments=[str(_schema(directory=tmp_path, content={"pattern": pattern}))], cwd=tmp_path)
    assert result.returncode == 1
    assert f"/pattern: {_U_FLAG_NODE} cannot read the pattern" in result.stdout
    assert _NODE_UNREADABLE not in result.stdout
    assert _PYTHON_UNREADABLE not in result.stdout


@_NEEDS_NODE
def test_a_schema_without_patterns_fails_the_check(*, tmp_path: Path) -> None:
    """A check that finds nothing to compare fails, so a broken search cannot pass for success."""
    result = _run(arguments=[str(_schema(directory=tmp_path, content={"type": "string"}))], cwd=tmp_path)
    assert (result.returncode, result.stdout) == (1, "no pattern found, so nothing was checked\n")


@_NEEDS_NODE
def test_a_missing_schema_file_fails_the_check(*, tmp_path: Path) -> None:
    """The check names the file it could not read."""
    missing = tmp_path / "missing.json"
    result = _run(arguments=[str(missing)], cwd=tmp_path)
    assert result.returncode == 1
    assert str(missing) in result.stdout


@_NEEDS_NODE
def test_a_schema_file_that_is_not_json_fails_the_check(*, tmp_path: Path) -> None:
    """The check names the file it could not parse."""
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    result = _run(arguments=[str(broken)], cwd=tmp_path)
    assert result.returncode == 1
    assert str(broken) in result.stdout


def test_more_than_one_argument_is_a_usage_error(*, tmp_path: Path) -> None:
    """The check takes one optional schema path."""
    result = _run(arguments=["a.json", "b.json"], cwd=tmp_path)
    assert (result.returncode, result.stdout) == (2, "")
    assert _USAGE in result.stderr


def test_a_missing_node_fails_the_check_rather_than_skipping_it(*, tmp_path: Path) -> None:
    """Without Node there is nothing to compare with, so the hook fails with the shell's code for a missing command."""
    schema = _schema(directory=tmp_path, content={"pattern": "[a-z]"})
    result = _run(arguments=[str(schema)], cwd=tmp_path, path=str(tmp_path / "empty"))
    assert (result.returncode, result.stdout) == (127, "")
    assert _NODE_NOT_FOUND in result.stderr


@pytest.mark.parametrize(
    ("program", "message"),
    [
        pytest.param(_FAILING_NODE, "node exited with code 3: boom", id="node-crashes"),
        pytest.param(_SILLY_NODE, "node answered with text that is not JSON", id="node-answers-in-prose"),
    ],
)
def test_a_node_that_fails_or_answers_badly_fails_the_check(*, tmp_path: Path, program: str, message: str) -> None:
    """The check reports what Node did and fails, whatever it was."""
    bin_directory = tmp_path / "bin"
    bin_directory.mkdir()
    _install_fake_node(directory=bin_directory, program=program)
    schema = _schema(directory=tmp_path, content={"pattern": "[a-z]"})
    result = _run(arguments=[str(schema)], cwd=tmp_path, path=str(bin_directory))
    assert result.returncode == 1
    assert message in result.stdout


def _hook() -> dict[str, str]:
    """Read the settings of the pre-commit hook that runs the check, failing when it is missing or listed twice.

    The configuration is YAML, and the project has no YAML parser with type stubs, so this reads its lines of the form
    `key: value` between the hook's own id and the next one.
    """
    blocks = [
        block for block in _PRE_COMMIT_CONFIG.read_text(encoding="utf-8").split("- id: ") if block.startswith(_HOOK_ID)
    ]
    assert len(blocks) == 1
    return dict(_SETTING.findall(blocks[0]))


def test_the_hook_runs_the_check_on_the_default_schema_without_file_arguments() -> None:
    """The hook is the only enforcement where Node is missing from the test image, so its definition is pinned."""
    hook = _hook()
    assert (hook["language"], hook["entry"], hook["pass_filenames"], hook["stages"]) == (
        "system",
        _HOOK_ENTRY,
        "false",
        "[pre-commit]",
    )
    assert _SCRIPT.is_file()


@pytest.mark.parametrize(
    ("path", "runs"),
    [
        pytest.param("schemas/pyrigor-diagnostics-v2.json", True, id="the-schema"),
        pytest.param("scripts/check_schema_pattern_portability.py", True, id="the-check"),
        pytest.param("schemas/another.json", True, id="another-schema"),
        pytest.param("README.md", False, id="documentation"),
        pytest.param("tests/test_schema_pattern_portability.py", False, id="a-test"),
        pytest.param("scripts/check_text_hygiene.py", False, id="another-script"),
    ],
)
def test_the_hook_runs_when_a_schema_or_the_check_changes(*, path: str, runs: bool) -> None:
    """The hook's file filter matches the schemas and the check itself, and nothing else."""
    assert bool(re.search(json.loads(_hook()["files"]), path)) is runs
