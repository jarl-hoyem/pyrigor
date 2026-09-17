"""Shared support for the tests of the v2 diagnostics schema and of the finding types that implement it."""

import json
from pathlib import Path
from typing import Any, cast

import jsonschema
import pytest
from jsonschema.protocols import Validator

from pyrigor.findings import FileName

# JSON documents are untyped by nature. Any matches the jsonschema stubs' own instance type.
Json = dict[str, Any]

REPOSITORY_ROOT = Path(__file__).parent.parent
V2_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "pyrigor-diagnostics-v2.json"
FILE_NAME = FileName("src/app.py")
_ROOT_REJECTION = "not"


def require_schema_file(*, path: Path) -> None:
    """Fail, rather than skip, when the schema file is missing."""
    if not path.is_file():
        pytest.fail(f"schema file not found: {path}")


def load_v2_schema() -> Json:
    """Load the v2 schema, failing when it is missing."""
    require_schema_file(path=V2_SCHEMA_PATH)
    return cast("Json", json.loads(V2_SCHEMA_PATH.read_text(encoding="utf-8")))


def definition_validator(*, definition: str) -> Validator:
    """Build a validator for one definition, without the root's rejection of every document."""
    schema = {key: value for key, value in load_v2_schema().items() if key != _ROOT_REJECTION}
    return jsonschema.Draft202012Validator({**schema, "$ref": f"#/$defs/{definition}"})
