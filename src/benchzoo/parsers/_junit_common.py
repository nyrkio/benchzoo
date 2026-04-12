"""Shared helpers for per-producer junit XML parsers.

All benchzoo junit parsers (``junit_pytest``, ``junit_jest``,
``junit_go``, ``junit_vanilla``, ...) read pytest-produced junit XML
and fall back to each ``<testcase>``'s ``time`` attribute as a
``duration`` metric when there are no producer-specific
``<properties>``. What differs between producers is primarily the
``test_name`` normalization (strip ``test_`` for pytest, strip
``Test`` + lowercase for go, no transform for jest).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Callable


def parse_junit(
    content: bytes | str,
    *,
    normalize_name: Callable[[str], str] = lambda s: s,
) -> list[dict]:
    """Parse junit XML, returning one Nyrkiö dict per ``<testcase>``.

    ``normalize_name`` transforms the testcase's ``name`` attribute
    into the canonical Nyrkiö ``attributes["test_name"]``. Defaults to
    the identity transform.
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    root = ET.fromstring(content)

    out: list[dict] = []
    # junit XML allows <testsuites> wrapping <testsuite>s or bare <testsuite>.
    if root.tag == "testsuite":
        suites = [root]
    else:
        suites = root.findall("testsuite")

    for suite in suites:
        for testcase in suite.findall("testcase"):
            name_raw = testcase.get("name", "").strip()
            test_name = normalize_name(name_raw)

            time_s = float(testcase.get("time", "0") or 0)

            failed = (
                testcase.find("failure") is not None
                or testcase.find("error") is not None
            )

            out.append({
                "timestamp": 0,
                "attributes": {"test_name": test_name},
                "metrics": [
                    {
                        "name": "duration",
                        "unit": "s",
                        "value": time_s,
                        "direction": "lower_is_better",
                    }
                ],
                "passed": not failed,
            })

    return out
