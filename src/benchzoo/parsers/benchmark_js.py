"""Parser for the benchmark.js sample benchmark's JSON output.

The JSON shape is defined by our ``sample-benchmark.js`` emitter — not
by benchmark.js's own reporter (benchmark.js has no built-in JSON
output). The shape is::

    {
      "framework": "benchmark.js",
      "version": "2.1.4",
      "month": 4,
      "results": [
        {
          "name":     "benchmark1",
          "hz":        0.4646,        # ops per second
          "mean":      2.152,         # SECONDS per op (!)
          "rme":       0.023,         # relative margin of error, %
          "deviation": 0.0007,        # stddev, seconds
          "variance":  5.3e-7,
          "moe":       0.0005,        # margin of error, seconds
          "sem":       0.00022,       # standard error of the mean, seconds
          "samples":   11,
          "cycles":    1,
          "deferred":  true,
          "passed":    true
        },
        ...
      ]
    }

**Important unit note:** benchmark.js reports ``mean`` in **seconds**
per operation, not milliseconds. The pretty-printer adds human-readable
suffixes like ``"2.15s"`` or ``"6µs"`` but the raw numeric field is
always seconds.

See ``frameworks/language/benchmark-js/README.md``.
"""

from __future__ import annotations

import json


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    out: list[dict] = []
    for entry in doc.get("results", []):
        metrics = [
            {"name": "mean",      "unit": "s",     "value": entry["mean"],      "direction": "lower_is_better"},
            {"name": "deviation", "unit": "s",     "value": entry["deviation"], "direction": "lower_is_better"},
            {"name": "moe",       "unit": "s",     "value": entry["moe"],       "direction": "lower_is_better"},
            {"name": "sem",       "unit": "s",     "value": entry["sem"],       "direction": "lower_is_better"},
            {"name": "hz",        "unit": "ops/s", "value": entry["hz"],        "direction": "higher_is_better"},
            {"name": "rme",       "unit": "%",     "value": entry["rme"]},
        ]
        out.append({
            "timestamp": 0,
            "attributes": {"test_name": entry["name"]},
            "metrics": metrics,
            "extra_info": {
                "samples": entry["samples"],
                "cycles": entry["cycles"],
                "deferred": entry.get("deferred", False),
            },
            "passed": entry.get("passed", True),
        })

    return out
