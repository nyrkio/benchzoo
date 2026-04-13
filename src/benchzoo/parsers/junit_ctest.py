"""Parser for CTest's ``--output-junit`` XML.

CTest emits a plain-vanilla junit structure with no producer-specific
extensions — just ``<testcase name="..." time="...">`` elements. Our
:mod:`junit_vanilla` parser is exactly the right tool; this module is
a thin delegator for discoverability (users reaching for "ctest"
should find a parser by name).

See ``frameworks/unit-or-qa/ctest/README.md``.
"""

from __future__ import annotations

from benchzoo.parsers import junit_vanilla


def parse(content: bytes | str) -> list[dict]:
    return junit_vanilla.parse(content)
