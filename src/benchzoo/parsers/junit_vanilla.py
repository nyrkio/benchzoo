"""Fallback parser for generic junit XML (no producer-specific knowledge).

This is the parser to reach for when the producer is unknown or has
no dedicated benchzoo parser. It reads testcase ``name`` and ``time``
attributes verbatim — no prefix stripping, no name transformation.

Per ``docs/parser-targets.md`` section 6, per-producer parsers are
preferred where available because they can extract richer data (e.g.
pytest-benchmark's ``<properties>``). Use ``junit_vanilla`` only as
the fallback for raw Java JUnit / Maven Surefire / anything else.

See ``frameworks/unit-or-qa/junit-vanilla/README.md``.
"""

from __future__ import annotations

from benchzoo.parsers._junit_common import parse_junit


def parse(content: bytes | str) -> list[dict]:
    return parse_junit(content)
