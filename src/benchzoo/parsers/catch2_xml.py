"""Parser for Catch2's native XML reporter output.

Catch2 v3's XML reporter emits ``<Catch2TestRun>`` with one
``<TestCase>`` per test. Benchmark-mode test cases have a
``<BenchmarkResults>`` child with the statistics we want::

    <BenchmarkResults name="benchmark1" samples="3" resamples="100000"
                      iterations="1" clockResolution="18.0474"
                      estimatedDuration="6.45052e+09">
      <!-- All values in nano seconds -->
      <mean value="2.15012e+09" lowerBound="2.15007e+09" upperBound="2.15016e+09" ci="0.95"/>
      <standardDeviation value="49369.3" lowerBound="0" upperBound="55845.4" ci="0.95"/>
      <outliers variance="0.222222" lowMild="0" lowSevere="0" highMild="0" highSevere="0"/>
    </BenchmarkResults>

All values are nanoseconds (per the XML's own comment).

Note: Catch2's ``--reporter json`` and ``--reporter junit`` produce
structured output for test assertions but **do not include
BenchmarkResults** — only the native XML reporter exposes benchmark
statistics. Use this parser for benchmark mode; if you want junit
parsing for Catch2 assertion-based tests, point ``junit_standard`` at
the junit output.

See ``frameworks/language/catch2/README.md``.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    root = ET.fromstring(content)

    out: list[dict] = []
    for test_case in root.findall("TestCase"):
        name = test_case.get("name", "")
        bench = test_case.find("BenchmarkResults")
        if bench is None:
            # Skip non-benchmark tests (plain assertion-based cases).
            continue

        mean_el = bench.find("mean")
        stddev_el = bench.find("standardDeviation")
        overall = test_case.find("OverallResult")
        passed = True if overall is None else overall.get("success", "true") == "true"

        metrics: list[dict] = []
        if mean_el is not None:
            metrics.append({
                "name": "mean",
                "unit": "ns",
                "value": float(mean_el.get("value", "0")),
                "direction": "lower_is_better",
            })
        if stddev_el is not None:
            metrics.append({
                "name": "stddev",
                "unit": "ns",
                "value": float(stddev_el.get("value", "0")),
                "direction": "lower_is_better",
            })

        params = {
            "samples": int(bench.get("samples", "0") or 0),
            "iterations": int(bench.get("iterations", "0") or 0),
            "resamples": int(bench.get("resamples", "0") or 0),
        }

        out.append({
            "test": {"test_name": name, "params": params},
            "run": {"passed": passed},
            "env": {"framework": {"name": "catch2"}},
            "metrics": metrics,
        })

    return out
