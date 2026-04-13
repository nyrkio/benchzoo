"""Parser for memtier_benchmark's ``--json-out-file`` output.

memtier's JSON has three top-level dicts of interest: ``configuration``,
``run information``, and ``"ALL STATS"`` (note the space and quotes —
this is a JSON key with a space). Under ``ALL STATS`` are keys like
``Runtime``, ``Sets``, ``Gets``, ``Totals`` (for Redis) or
``Sets``/``Gets``/``Totals`` for memcached too.

Each operation type dict contains flat float fields (not a nested
``Latency`` object as earlier memtier versions had)::

    {
      "Count":            108590,
      "Ops/sec":          27127.17,
      "Hits/sec":         0.0,
      "Misses/sec":       0.0,
      "Latency":          0.461,       # same as Average Latency
      "Average Latency":  0.461,
      "Min Latency":      0.032,
      "Max Latency":      9.343,
      "KB/sec":           2937.46,
      "Percentile Latencies": {
        "p50.00":  0.391,
        "p99.00":  1.775,
        "p99.90":  3.183,
        "Histogram log format": "..."   # not a percentile; skip
      }
    }

Parser emits one Nyrkiö dict per non-Runtime operation group. Latency
percentiles are renamed from ``p50.00`` → ``latency_p50``, ``p99.90``
→ ``latency_p999``, etc.

All latencies are in **milliseconds**.

See ``frameworks/database/memtier/README.md``.
"""

from __future__ import annotations

import json


import re


# Top-level latency fields (not under "Percentile Latencies").
_FLAT_LATENCY_KEYS = {
    "Average Latency": "latency_mean",
    "Min Latency":     "latency_min",
    "Max Latency":     "latency_max",
}


def _pct_to_metric_name(key: str) -> str | None:
    """'p50.00' → 'latency_p50', 'p99.90' → 'latency_p999'.

    Returns None for non-percentile keys (e.g. 'Histogram log format').
    """
    m = re.match(r"^p(\d+(?:\.\d+)?)$", key)
    if not m:
        return None
    pct = m.group(1).rstrip("0").rstrip(".")
    return "latency_p" + pct.replace(".", "")


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    all_stats = doc.get("ALL STATS", {})

    out: list[dict] = []
    for op_name, stats in all_stats.items():
        if op_name == "Runtime":
            continue
        if not isinstance(stats, dict):
            continue

        test_name = op_name.lower()

        metrics: list[dict] = []

        # Throughput.
        if "Ops/sec" in stats:
            metrics.append({"name": "ops_per_sec", "unit": "ops/s",
                            "value": stats["Ops/sec"], "direction": "higher_is_better"})
        if "KB/sec" in stats:
            metrics.append({"name": "kb_per_sec", "unit": "kB/s",
                            "value": stats["KB/sec"], "direction": "higher_is_better"})
        if "Hits/sec" in stats:
            metrics.append({"name": "hits_per_sec", "unit": "ops/s",
                            "value": stats["Hits/sec"]})
        if "Misses/sec" in stats:
            metrics.append({"name": "misses_per_sec", "unit": "ops/s",
                            "value": stats["Misses/sec"],
                            "direction": "lower_is_better"})

        # Flat latency fields at the op level.
        for key, metric_name in _FLAT_LATENCY_KEYS.items():
            if key in stats:
                metrics.append({"name": metric_name, "unit": "ms",
                                "value": stats[key],
                                "direction": "lower_is_better"})

        # Percentile histogram under "Percentile Latencies".
        pcts = stats.get("Percentile Latencies", {})
        if isinstance(pcts, dict):
            for key, value in pcts.items():
                metric_name = _pct_to_metric_name(key)
                if metric_name is None:
                    continue
                metrics.append({"name": metric_name, "unit": "ms",
                                "value": value,
                                "direction": "lower_is_better"})

        out.append({
            "timestamp": 0,
            "attributes": {"test_name": test_name},
            "metrics": metrics,
            "passed": True,
        })

    return out
