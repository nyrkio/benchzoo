"""Shared helpers for per-producer junit XML parsers.

Three benchzoo parsers layer on top of this helper:

- :mod:`junit_standard` — the canonical verbatim reader (no name
  transform). Covers jest-junit, Maven Surefire / vanilla Java JUnit,
  CTest, and Catch2's junit reporter.
- :mod:`junit_go` — strips gotestsum's ``Test`` prefix and lowercases.
- :mod:`junit_pytest` — reads pytest-benchmark's ``<properties>`` for
  richer metrics when present.
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
