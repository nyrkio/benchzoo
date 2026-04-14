"""Parser for BenchmarkDotNet's ``[JsonExporter] Full`` output.

BenchmarkDotNet emits a top-level JSON document with
``HostEnvironmentInfo`` (machine/runtime metadata) and a ``Benchmarks``
array. Each entry has, among other things::

    {
      "Namespace":  "BenchzooSample",
      "Type":       "SampleBenchmark",
      "Method":     "Benchmark1",
      "FullName":   "BenchzooSample.SampleBenchmark.Benchmark1",
      "Statistics": {
        "OriginalValues": [ ... raw per-iteration values ... ],
        "N": 3,
        "Min":    2150122705,
        "Q1":     2150122887,
        "Median": 2150123069,
        "Mean":   2150230735.666,
        "Q3":     2150284751,
        "Max":    2150446433,
        "StandardDeviation": 186799.45,
        ...
      }
    }

**All Statistics values are in nanoseconds.** This is BenchmarkDotNet's
internal resolution regardless of what the text pretty-printer renders
(the CSV exporter, for example, renders in μs). Parsers should emit
``unit: "ns"`` without any rescaling.

test_name is derived from ``Method`` (e.g. ``"Benchmark1"``) —
normalized to lowercase so it matches the canonical ``"benchmark1"``
naming used across the benchzoo corpus.

See ``frameworks/language/benchmarkdotnet/README.md``.
"""

from __future__ import annotations

import json


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    host = doc.get("HostEnvironmentInfo") or {}
    env: dict = {}
    if host.get("OsVersion"):
        env["os"] = host["OsVersion"]
    if host.get("Architecture"):
        env["arch"] = host["Architecture"]
    if host.get("ProcessorName"):
        env["cpu"] = host["ProcessorName"]
    if host.get("LogicalCoreCount"):
        env["cpu_count"] = host["LogicalCoreCount"]
    if host.get("RuntimeVersion"):
        env["runtime"] = host["RuntimeVersion"]
    framework = {"name": "benchmarkdotnet"}
    if host.get("BenchmarkDotNetVersion"):
        framework["version"] = host["BenchmarkDotNetVersion"]
    env["framework"] = framework

    extras = {}
    for k in ("PhysicalProcessorCount", "PhysicalCoreCount", "HasRyuJit",
              "Configuration", "DotNetCliVersion"):
        if host.get(k) is not None:
            extras[k] = host[k]

    out: list[dict] = []
    for entry in doc.get("Benchmarks", []):
        method = entry.get("Method", "")
        # Normalize "Benchmark1" → "benchmark1" for cross-framework
        # consistency with the canonical test_name.
        test_name = method[:1].lower() + method[1:] if method else ""

        test: dict = {"test_name": test_name}
        group_parts = [p for p in (entry.get("Namespace"), entry.get("Type")) if p]
        if group_parts:
            test["group"] = ".".join(group_parts)
        params_str = entry.get("Parameters") or ""
        if params_str:
            test["params"] = {"Parameters": params_str}

        stats = entry.get("Statistics", {})
        metrics = [
            {"name": "mean",   "unit": "ns", "value": stats["Mean"],              "direction": "lower_is_better"},
            {"name": "min",    "unit": "ns", "value": stats["Min"],               "direction": "lower_is_better"},
            {"name": "max",    "unit": "ns", "value": stats["Max"],               "direction": "lower_is_better"},
            {"name": "median", "unit": "ns", "value": stats["Median"],            "direction": "lower_is_better"},
            {"name": "stddev", "unit": "ns", "value": stats["StandardDeviation"], "direction": "lower_is_better"},
        ]

        result: dict = {
            "test": test,
            "run": {"passed": True},
            "env": env,
            "metrics": metrics,
        }
        if extras:
            result["extra_info"] = dict(extras)
        out.append(result)

    return out
