"""Shared helpers for per-producer junit XML parsers.

Three benchzoo parsers layer on top of this helper:

- :mod:`junit_standard` — the canonical verbatim reader (no name
  transform). Covers jest-junit, Maven Surefire / vanilla Java JUnit,
  CTest, and Catch2's junit reporter.
- :mod:`junit_go` — strips gotestsum's ``Test`` prefix and lowercases.
- :mod:`junit_pytest` — reads pytest-benchmark's ``<properties>`` for
  richer metrics when present.

Emits the v2 result schema (see ``docs/schema-v2.md``).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Callable


def parse_junit(
    content: bytes | str,
    *,
    framework_name: str,
    normalize_name: Callable[[str], str] = lambda s: s,
) -> list[dict]:
    """Parse junit XML, returning one Nyrkiö v2 dict per ``<testcase>``.

    ``framework_name`` is the kebab-case registry name to stamp at
    ``env.framework.name`` (e.g. ``"junit-standard"``, ``"junit-go"``,
    ``"pytest-benchmark"``).

    ``normalize_name`` transforms the testcase's ``name`` attribute
    into the canonical Nyrkiö ``test.test_name``. Defaults to the
    identity transform.

    The testcase's ``classname`` attribute — when present and
    non-empty — becomes ``test.group``. For benchmark contexts this
    is the honest mapping: suite / test-class / file-path grouping,
    not a description of the system under test.
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

            test: dict = {"test_name": test_name}
            classname = (testcase.get("classname") or "").strip()
            if classname:
                test["group"] = classname

            out.append({
                "test": test,
                "run": {"passed": not failed},
                "env": {"framework": {"name": framework_name}},
                "metrics": [
                    {
                        "name": "duration",
                        "unit": "s",
                        "value": time_s,
                        "direction": "lower_is_better",
                    }
                ],
            })

    return out
