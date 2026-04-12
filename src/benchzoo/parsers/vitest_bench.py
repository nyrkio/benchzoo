"""Parser for vitest's ``--outputJson`` bench mode output.

vitest's bench reporter produces a top-level object with a ``files``
array. Each file has one or more ``groups`` (from ``describe()``
blocks), and each group has a ``benchmarks`` array. Each benchmark
entry is a tinybench ``Task`` result::

    {
      "id":        "-1794347567_0_0",
      "name":      "benchmark1",
      "rank":      4,
      "rme":       0.0017,
      "samples":   [ ... ],
      "totalTime": 6457.22,
      "min":       2152.39,
      "max":       2152.42,
      "hz":        0.4645,       # ops/second
      "period":    2152.408,     # = mean, ms
      "mean":      2152.408,     # milliseconds per op
      "variance":  0.00021,
      "sd":        0.0145,       # stddev, ms
      "sem":       0.0084,
      "df":        2,
      "critical":  4.303,
      "moe":       0.036,
      "p75":       2152.425,
      "p99":       2152.425,
      "p995":      2152.425,
      "p999":      2152.425
    }

**Units are milliseconds** (tinybench's default), not seconds.

The ``describe()`` block name lands in ``extra_info["group"]``
(following the grouping convention in ``docs/design.md``).

See ``frameworks/language/vitest-bench/README.md``.
"""

from __future__ import annotations

import json


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    out: list[dict] = []
    for file_entry in doc.get("files", []):
        for group in file_entry.get("groups", []):
            group_name = group.get("fullName") or group.get("name") or ""
            for bench in group.get("benchmarks", []):
                metrics = [
                    {"name": "mean",   "unit": "ms",    "value": bench["mean"], "direction": "lower_is_better"},
                    {"name": "min",    "unit": "ms",    "value": bench["min"],  "direction": "lower_is_better"},
                    {"name": "max",    "unit": "ms",    "value": bench["max"],  "direction": "lower_is_better"},
                    {"name": "stddev", "unit": "ms",    "value": bench["sd"],   "direction": "lower_is_better"},
                    {"name": "p75",    "unit": "ms",    "value": bench["p75"],  "direction": "lower_is_better"},
                    {"name": "p99",    "unit": "ms",    "value": bench["p99"],  "direction": "lower_is_better"},
                    {"name": "hz",     "unit": "ops/s", "value": bench["hz"],   "direction": "higher_is_better"},
                    {"name": "rme",    "unit": "%",     "value": bench["rme"]},
                ]
                extra_info = {
                    "samples": len(bench.get("samples", [])),
                }
                if group_name:
                    extra_info["group"] = group_name
                out.append({
                    "timestamp": 0,
                    "attributes": {"test_name": bench["name"]},
                    "metrics": metrics,
                    "extra_info": extra_info,
                    "passed": True,
                })

    return out
