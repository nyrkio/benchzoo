"""Parser for Jest's jest-junit XML output.

Per-producer junit parser (parser-targets.md section 6). Jest test
names appear verbatim as the ``<testcase name="...">`` attribute;
our sample uses ``benchmark1``..``benchmark4`` directly, so no prefix
stripping is needed. However jest-junit leaves a leading space in
the ``name`` attribute (``" benchmark1"``), which the shared helper
strips.

See ``frameworks/unit-or-qa/junit-jest/README.md``.
"""

from __future__ import annotations

from benchzoo.parsers._junit_common import parse_junit


def parse(content: bytes | str) -> list[dict]:
    return parse_junit(content)
