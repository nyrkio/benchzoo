"""Parser for ``dotnet test --logger trx`` TRX XML output.

TRX (Visual Studio Test Results) is Microsoft's native test-result
XML. Top-level ``<TestRun>`` wraps ``<Results><UnitTestResult ...>``
elements::

    <UnitTestResult
        testName="BenchzooSample.SampleTests.Benchmark1"
        duration="00:00:02.1501913"
        outcome="Passed" />

Durations are ``hh:mm:ss.fffffff`` (7 fractional digits = 100 ns
ticks). We convert to seconds.

``testName`` is fully-qualified (``Namespace.Class.Method``). We
take the final dotted segment and lowercase the first letter so
``Benchmark1`` → ``benchmark1`` for cross-framework consistency.

TRX uses the ``http://microsoft.com/schemas/VisualStudio/TeamTest/2010``
XML namespace, which ElementTree preserves on tag names — we query
with wildcard namespaces via ``{*}TagName``.

See ``frameworks/unit-or-qa/dotnet-test/README.md``.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET


_DURATION_RE = re.compile(r"^(\d+):(\d+):(\d+(?:\.\d+)?)$")


def _duration_to_seconds(raw: str) -> float:
    m = _DURATION_RE.match(raw.strip())
    if not m:
        raise ValueError(f"unparseable TRX duration: {raw!r}")
    h, mm, ss = m.group(1), m.group(2), m.group(3)
    return int(h) * 3600 + int(mm) * 60 + float(ss)


def _short_test_name(full: str) -> str:
    tail = full.rsplit(".", 1)[-1]
    return tail[:1].lower() + tail[1:] if tail else tail


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    root = ET.fromstring(content)

    # TRX uses a fixed XML namespace on all its elements. iter()'s
    # wildcard '{*}TagName' syntax is for findall paths, not raw iter —
    # we extract the namespace from the root tag and filter manually.
    ns_match = root.tag[1:].split("}", 1)[0] if root.tag.startswith("{") else ""
    utr_tag = f"{{{ns_match}}}UnitTestResult" if ns_match else "UnitTestResult"

    out: list[dict] = []
    for result in root.iter(utr_tag):
        name_raw = result.get("testName", "")
        if not name_raw:
            continue
        test_name = _short_test_name(name_raw)
        duration_s = _duration_to_seconds(result.get("duration", "00:00:00"))
        outcome = result.get("outcome", "Passed")
        passed = outcome == "Passed"

        extra_info: dict = {}
        if name_raw != test_name:
            extra_info["full_name"] = name_raw
        if outcome and outcome != "Passed":
            extra_info["outcome"] = outcome

        result_dict = {
            "timestamp": 0,
            "attributes": {"test_name": test_name},
            "metrics": [{
                "name": "duration",
                "unit": "s",
                "value": duration_s,
                "direction": "lower_is_better",
            }],
            "passed": passed,
        }
        if extra_info:
            result_dict["extra_info"] = extra_info
        out.append(result_dict)

    return out
