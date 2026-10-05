"""Shared support for the v2 diagnostics tests.

It serves the schema tests and the tests of the finding types that implement the schema.
"""

import json
import re
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
HIDDEN_TEXT_DEFINITION = "TextWithoutHiddenCharacters"
HIDDEN_TEXT_REFERENCE = {"$ref": f"#/$defs/{HIDDEN_TEXT_DEFINITION}"}
_SURROGATES = range(0xD800, 0xE000)


def require_schema_file(*, path: Path) -> None:
    """Fail, rather than skip, when the schema file is missing."""
    if not path.is_file():
        pytest.fail(f"schema file not found: {path}")


def load_v2_schema() -> Json:
    """Load the v2 schema, failing when it is missing."""
    require_schema_file(path=V2_SCHEMA_PATH)
    return cast("Json", json.loads(V2_SCHEMA_PATH.read_text(encoding="utf-8")))


def definition_validator(*, definition: str) -> Validator:
    """Build a validator for one definition, independently of the document root."""
    schema = load_v2_schema()
    return jsonschema.Draft202012Validator(
        {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": f"#/$defs/{definition}"}
    )


def hidden_character_classes() -> dict[str, str]:
    """Map each rule of the schema's shared hidden-character definition to the character class it forbids."""
    rules = load_v2_schema()["$defs"][HIDDEN_TEXT_DEFINITION]["allOf"]
    return {rule["description"]: rule["not"]["pattern"] for rule in rules}


def forbidden_hidden_characters() -> set[str]:
    """List every character the shared definition forbids, found by matching its classes against all code points."""
    every_character = "".join(chr(code_point) for code_point in range(0x110000) if code_point not in _SURROGATES)
    return set(re.findall("|".join(hidden_character_classes().values()), every_character))
