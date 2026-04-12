"""Parser for the tinybench sample benchmark's JSON output.

Our ``sample-benchmark.js`` emits a JSON envelope around each
tinybench ``Task.result``::

    {
      "framework": "tinybench",
      "version": "3.0.6",
      "month": 4,
      "results": [
        {
          "name": "benchmark1",
          "hz": 0.4647,
          "latency": {
            "mean":   2151.78,      # milliseconds
            "min":    2150.74,
            "max":    2152.31,
            "p50":    2152.30,
            "p75":    2152.31,
            "p99":    2152.31,
            "p995":   2152.31,
            "p999":   2152.31,
            "sd":     0.78,
            "rme":    0.10,
            "moe":    2.24,
            "samples": [ ... raw values ... ]
          },
          ...
        },
        ...
      ]
    }

**Note**: tinybench 3.x nests timing stats under ``latency``.
tinybench 2.x exposed them at the top level (that's what vitest-bench
2.1.x — which embeds tinybench — looks like). The vitest-bench parser
could be migrated to this shape once vitest upgrades its tinybench
dependency; for now they are separate modules.

Units are **milliseconds**.

See ``frameworks/language/tinybench/README.md``.
"""

from __future__ import annotations

import json


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    out: list[dict] = []
    for entry in doc.get("results", []):
        latency = entry.get("latency", {})
        metrics = [
            {"name": "mean",   "unit": "ms",    "value": latency["mean"], "direction": "lower_is_better"},
            {"name": "min",    "unit": "ms",    "value": latency["min"],  "direction": "lower_is_better"},
            {"name": "max",    "unit": "ms",    "value": latency["max"],  "direction": "lower_is_better"},
            {"name": "p50",    "unit": "ms",    "value": latency["p50"],  "direction": "lower_is_better"},
            {"name": "p75",    "unit": "ms",    "value": latency["p75"],  "direction": "lower_is_better"},
            {"name": "p99",    "unit": "ms",    "value": latency["p99"],  "direction": "lower_is_better"},
            {"name": "stddev", "unit": "ms",    "value": latency["sd"],   "direction": "lower_is_better"},
            {"name": "hz",     "unit": "ops/s", "value": entry["hz"],     "direction": "higher_is_better"},
            {"name": "rme",    "unit": "%",     "value": latency["rme"]},
        ]
        # sample-benchmark.js strips raw `samples` arrays (they can
        # reach millions of entries for sub-microsecond benchmarks and
        # would blow through GitHub's 100 MB per-file limit), replacing
        # each with `samples_count`. Prefer that count; fall back to
        # measuring the samples array if the emit script is older.
        samples_count = (
            latency.get("samples_count")
            or len(latency.get("samples", []))
        )
        out.append({
            "timestamp": 0,
            "attributes": {"test_name": entry["name"]},
            "metrics": metrics,
            "extra_info": {"samples": samples_count},
            "passed": True,
        })

    return out
