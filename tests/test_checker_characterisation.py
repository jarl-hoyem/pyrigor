"""Freeze raw checker detections against a portable pre-migration source corpus."""

import ast
import io
import json
from pathlib import Path
from typing import NamedTuple
from zipfile import ZipFile

from pyrigor.checkers import CHECKERS, walk_once
from pyrigor.finding_builder import FindingContext
from pyrigor.findings import FileName, Finding, PositionIndex
from pyrigor.suppression import filter_suppressed


class _CorpusRecords(NamedTuple):
    """Raw detections and their suppression membership for one frozen source."""

    raw: list[dict[str, str | int]]
    kept: list[dict[str, str | int]]
    suppressed: list[dict[str, str | int]]


def _records(*, findings: list[Finding], file_name: str) -> list[dict[str, str | int]]:
    """Project detections to the pre-migration snapshot's stable identity fields."""
    return [{"file": file_name, "code": finding.code.name, "line": finding.spans[0].line_start} for finding in findings]


def _check_source(*, raw: bytes, file_name: str) -> _CorpusRecords:
    """Run current checkers and suppression against original frozen source bytes."""
    with io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8-sig") as stream:
        source = stream.read()
    nodes = walk_once(tree=ast.parse(source))
    context = FindingContext(
        source=source,
        index=PositionIndex(raw=raw),
        file_name=FileName(file_name),
        parents=nodes.parents,
    )
    findings = [finding for checker in CHECKERS for finding in checker.find_findings(nodes=nodes, context=context)]
    result = filter_suppressed(findings=findings, source=source, tokens=context.tokens if findings else None)
    return _CorpusRecords(
        raw=_records(findings=findings, file_name=file_name),
        kept=_records(findings=result.kept, file_name=file_name),
        suppressed=_records(findings=result.suppressed, file_name=file_name),
    )


def test_raw_checker_detections_match_frozen_corpus() -> None:
    """Preserve every file, rule and starting line, including suppression membership.

    The archive contains committed UTF-8 Python files from pyrigor/, tests/checkers/
    and manual-tests/ at 032c900. Unparsable files are listed in the snapshot and
    excluded from the archive. Its bytes do not change when live sources migrate.
    """
    fixtures = Path(__file__).parent / "fixtures"
    expected = json.loads((fixtures / "checker-corpus-032c900.json").read_text(encoding="utf-8"))
    records: list[dict[str, str | int]] = []
    kept_records: list[dict[str, str | int]] = []
    suppressed_records: list[dict[str, str | int]] = []
    with ZipFile(fixtures / "checker-corpus-032c900.zip") as archive:
        assert len(archive.namelist()) == expected["files_checked"]
        for file_name in sorted(archive.namelist()):
            checked = _check_source(raw=archive.read(file_name), file_name=file_name)
            records.extend(checked.raw)
            kept_records.extend(checked.kept)
            suppressed_records.extend(checked.suppressed)
    records.sort(key=lambda record: (record["file"], record["code"], record["line"]))
    assert records == expected["records"]
    kept_records.sort(key=lambda record: (record["file"], record["code"], record["line"]))
    suppressed_records.sort(key=lambda record: (record["file"], record["code"], record["line"]))
    assert (
        kept_records,
        suppressed_records,
    ) == (
        expected["kept_records"],
        expected["suppressed_records"],
    )
