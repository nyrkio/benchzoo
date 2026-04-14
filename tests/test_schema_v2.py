"""Validate v2-schema parsers against docs/schema-v2.schema.json.

Only the parsers that have been converted to v2 are exercised here.
Adding a parser to ``V2_PARSERS`` is the signal that it now emits v2.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from jsonschema import Draft202012Validator

from benchzoo.parsers import pytest_benchmark_json


ROOT = pathlib.Path(__file__).parent.parent
SCHEMA = json.loads((ROOT / "docs" / "schema-v2.schema.json").read_text())
DATA = ROOT / "tests" / "data"


# Parsers converted to v2 are listed here as (module, fixture_path) pairs.
# Adding a parser to this list is the signal that it now emits v2.
V2_PARSERS = [
    (pytest_benchmark_json, DATA / "pytest-benchmark-output" / "output.json"),
]


def test_schema_is_itself_valid():
    Draft202012Validator.check_schema(SCHEMA)


@pytest.mark.parametrize("parser,fixture", V2_PARSERS, ids=lambda p: getattr(p, "__name__", str(p)))
def test_parser_emits_valid_v2(parser, fixture):
    results = parser.parse(fixture.read_bytes())
    validator = Draft202012Validator(SCHEMA)
    errors: list[str] = []
    for i, run in enumerate(results):
        for err in validator.iter_errors(run):
            errors.append(f"result[{i}] {list(err.absolute_path)}: {err.message}")
    assert not errors, "\n".join(errors)
