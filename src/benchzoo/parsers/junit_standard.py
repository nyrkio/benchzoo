"""Canonical parser for plain ``<testsuite>`` / ``<testsuites>`` junit XML.

Jest (jest-junit), Maven Surefire / vanilla Java JUnit, CTest
(``--output-junit``) and Catch2 (``--reporter junit``) all emit junit
XML that is structurally byte-equivalent for our purposes: testcase
names appear verbatim in the ``name`` attribute and wall-clock time in
the ``time`` attribute. We read both verbatim — no prefix stripping,
no name transformation.

Per-producer junit parsers still exist when the artifact carries extra
information: :mod:`junit_pytest` reads pytest-benchmark's
``<properties>``, and :mod:`junit_go` strips gotestsum's ``Test``
prefix. See ``docs/parser-targets.md`` section 6.
"""

from __future__ import annotations

from benchzoo.parsers._junit_common import parse_junit


def parse(content: bytes | str) -> list[dict]:
    return parse_junit(content, framework_name="junit-standard")
