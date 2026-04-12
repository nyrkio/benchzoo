"""Parser for k6's streaming ``--out json=output.json`` output.

k6's streaming output is newline-delimited JSON (ndjson). Two line
shapes matter for us:

- **Metric descriptor**::

    {"type": "Metric", "metric": "benchmark1",
     "data": {"name": "benchmark1", "type": "trend", ...}}

- **Point** — one observation of a metric::

    {"type": "Point", "metric": "benchmark1",
     "data": {"time": "2026-04-12T18:34:57.964341483Z",
              "value": 2151, "tags": {...}}}

The canonical sample benchmark uses ``iterations: 1``, so each of our
four Trends (``benchmark1`` .. ``benchmark4``) receives exactly one
Point. We aggregate across all Points per metric (trivially equal to
that single value when there's only one) and emit avg/min/max/median.

Like the summary parser, we skip k6's built-in metrics and only emit
dicts for the four custom Trends.

See ``frameworks/loadtest/k6/README.md``.
"""

from __future__ import annotations

import json
import re
import statistics


_BENCHMARK_NAME_RE = re.compile(r"^benchmark\d+$")


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    # Accumulate values per metric name.
    values: dict[str, list[float]] = {}
    for line in content.splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if obj.get("type") != "Point":
            continue
        name = obj.get("metric", "")
        if not _BENCHMARK_NAME_RE.match(name):
            continue
        values.setdefault(name, []).append(float(obj["data"]["value"]))

    out: list[dict] = []
    for name in sorted(values):
        samples = values[name]
        avg = sum(samples) / len(samples)
        median_val = statistics.median(samples)
        metrics = [
            {"name": "avg",    "unit": "ms", "value": avg,             "direction": "lower_is_better"},
            {"name": "min",    "unit": "ms", "value": min(samples),    "direction": "lower_is_better"},
            {"name": "median", "unit": "ms", "value": median_val,      "direction": "lower_is_better"},
            {"name": "max",    "unit": "ms", "value": max(samples),    "direction": "lower_is_better"},
        ]
        out.append({
            "timestamp": 0,
            "attributes": {"test_name": name},
            "metrics": metrics,
            "extra_info": {"samples": len(samples)},
            "passed": True,
        })

    return out
