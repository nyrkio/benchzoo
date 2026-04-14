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

import datetime as _dt
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
    ns_prefix = f"{{{ns_match}}}" if ns_match else ""
    utr_tag = f"{ns_prefix}UnitTestResult"
    times_tag = f"{ns_prefix}Times"

    run_base: dict = {"passed": True}
    times_el = root.find(times_tag)
    if times_el is not None:
        start = times_el.get("start")
        if start:
            try:
                run_base["test_time"] = int(_dt.datetime.fromisoformat(start).timestamp())
            except ValueError:
                pass

    env = {"framework": {"name": "dotnet-test"}}

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
        if outcome and outcome != "Passed":
            extra_info["outcome"] = outcome

        test: dict = {"test_name": test_name}
        if "." in name_raw:
            test["group"] = name_raw.rsplit(".", 1)[0]

        run = dict(run_base)
        run["passed"] = passed

        result_dict: dict = {
            "test": test,
            "run": run,
            "env": env,
            "metrics": [{
                "name": "duration",
                "unit": "s",
                "value": duration_s,
                "direction": "lower_is_better",
            }],
        }
        if extra_info:
            result_dict["extra_info"] = extra_info
        out.append(result_dict)

    return out
