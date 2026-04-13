"""Parser for Catch2's ``--reporter junit`` XML.

Catch2's junit reporter emits plain junit XML with no Catch2-specific
properties attached to benchmark mode. This module is a thin
delegator to :mod:`junit_vanilla`, kept as a named module so users
reaching for a "catch2 junit" parser find one.

**Note**: Catch2's *benchmark* results do NOT appear in its junit
output — only assertion-based test cases do. To parse Catch2
benchmark data, use :mod:`catch2_xml` against the native XML
reporter's output instead.

See ``frameworks/language/catch2/README.md``.
"""

from __future__ import annotations

from benchzoo.parsers import junit_vanilla


def parse(content: bytes | str) -> list[dict]:
    return junit_vanilla.parse(content)
