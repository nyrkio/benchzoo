"""Parser for asv (airspeed velocity) per-commit results JSON.

asv writes a single results file per commit per environment at
``.asv/results/<machine>/<hash>-<env>.json``. Its schema is unusual:
``result_columns`` declares column names, and ``results`` maps each
benchmark's fully-qualified name to a **positional** array of values
matching those columns::

    {
      "commit_hash": "...",
      "date": 1776026564000,
      "result_columns": ["result", "params", "version", "started_at",
                         "duration", "stats_ci_99_a", "stats_ci_99_b",
                         "stats_q_25", "stats_q_75", "stats_number",
                         "stats_repeat", "samples", "profile"],
      "results": {
        "benchmarks.SampleBenchmark.time_benchmark1": [
          [2.150080091],          # result: list (one per param combo)
          [],                      # params
          "<hash>",                # version
          1776026447699,          # started_at
          2.156,                   # duration
          [-Infinity], [Infinity], # stats_ci_99_a / b
          [2.1501], [2.1501],     # stats_q_25 / q_75
          [1], [1]                 # stats_number / repeat
        ],
        ...
      }
    }

Note: the values array may be truncated if trailing columns have no
data — ``samples`` and ``profile`` are commonly absent. Zip against
``result_columns[:len(values)]``.

All timing values are in **seconds**. ``test_name`` is derived by
taking the last dotted segment of the benchmark key and stripping the
``time_`` prefix (``benchmarks.SampleBenchmark.time_benchmark1`` →
``benchmark1``).

JSON caveat: asv writes ``-Infinity`` / ``Infinity`` literals which
are an extension to strict JSON. Python's ``json`` module accepts them
by default (they decode to ``float('-inf')`` / ``float('inf')``).

See ``frameworks/language/asv/README.md``.
"""

from __future__ import annotations

import json
import math


def _normalize_name(fq_name: str) -> str:
    """``benchmarks.SampleBenchmark.time_benchmark1`` → ``benchmark1``."""
    tail = fq_name.rsplit(".", 1)[-1]
    if tail.startswith("time_"):
        tail = tail[5:]
    return tail


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    columns = doc.get("result_columns", [])
    results = doc.get("results", {})

    out: list[dict] = []
    for fq_name, values in results.items():
        # Zip against truncated column list.
        row = dict(zip(columns[:len(values)], values))

        # ``result`` is a list of values, one per param combo. Our
        # benchmarks have no params, so there's exactly one element.
        result_list = row.get("result", [])
        if not result_list or result_list[0] is None:
            continue
        mean_seconds = result_list[0]

        metrics: list[dict] = [
            {
                "name": "mean",
                "unit": "s",
                "value": mean_seconds,
                "direction": "lower_is_better",
            },
        ]

        # Quartile stats (also per-param-combo lists).
        for key, metric_name in (("stats_q_25", "q25"), ("stats_q_75", "q75")):
            q = row.get(key)
            if q and q[0] is not None and not math.isinf(q[0]):
                metrics.append({
                    "name": metric_name,
                    "unit": "s",
                    "value": q[0],
                    "direction": "lower_is_better",
                })

        extra_info: dict = {}
        if "duration" in row:
            extra_info["total_duration"] = row["duration"]
        if "stats_number" in row and row["stats_number"]:
            extra_info["stats_number"] = row["stats_number"][0]
        if "stats_repeat" in row and row["stats_repeat"]:
            extra_info["stats_repeat"] = row["stats_repeat"][0]

        out.append({
            "timestamp": 0,
            "attributes": {"test_name": _normalize_name(fq_name)},
            "metrics": metrics,
            "extra_info": extra_info,
            "passed": True,
        })

    return out
