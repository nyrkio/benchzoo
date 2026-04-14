"""Parser for the canonical ClickBench JSON results format.

ClickBench (https://github.com/ClickHouse/ClickBench) is the de-facto
OLAP comparison benchmark. Each submission emits a single JSON file
with a top-level ``result`` field that is an **array of arrays** —
one inner array per query, containing that query's per-run wall
times in **seconds**::

    {
      "system":       "ClickHouse",
      "date":         "2026-04-12",
      "machine":      "c6a.4xlarge",
      "cluster_size": 1,
      "comment":      "...",
      "tags":         ["column-oriented", "OLAP", ...],
      "load_time":    5.2,          # seconds to ingest the dataset
      "data_size":    1000000,      # bytes on disk after loading
      "result": [
        [0.0403, 0.0444, 0.0394],   # query 1, three runs
        [0.0408, 0.0405, 0.0413],   # query 2
        ...
      ]
    }

Each inner array is one canonical query; full ClickBench has 43
queries but our benchzoo sample uses 5. test_name is ``q1``..``qN``
based on position (ClickBench queries are traditionally identified
by 0-based index, but we use 1-based to stay consistent with the
rest of the corpus).

A run that failed is emitted as ``"nan"`` or ``null`` in the array.
The parser emits those as a failed metric (``passed: False`` on the
test-results dict, metric value omitted).

``load_time`` and ``data_size`` are corpus-level properties, not
per-query — they go into each test run's ``extra_info`` so downstream
consumers can join them back to the per-query metrics.

See ``frameworks/database/clickbench/README.md``.
"""

from __future__ import annotations

import datetime as _dt
import json
import math


def _is_valid_time(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return False
    if isinstance(v, float) and math.isnan(v):
        return False
    return True


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    env: dict = {"framework": {"name": "clickbench"}}
    if doc.get("machine"):
        env["cpu"] = doc["machine"]
    if doc.get("cluster_size"):
        env["cpu_count"] = doc["cluster_size"]

    sut: dict = {}
    if doc.get("system"):
        sut["name"] = doc["system"]

    run_base: dict = {"passed": True}
    date_str = doc.get("date")
    if date_str:
        try:
            run_base["test_time"] = int(_dt.datetime.fromisoformat(date_str).timestamp())
        except ValueError:
            pass

    shared_params = {}
    if doc.get("data_size") is not None:
        shared_params["data_size"] = doc["data_size"]

    extras_shared: dict = {}
    if doc.get("load_time") is not None:
        extras_shared["load_time_s"] = doc["load_time"]
    if doc.get("tags"):
        extras_shared["tags"] = doc["tags"]
    if doc.get("comment"):
        extras_shared["comment"] = doc["comment"]

    out: list[dict] = []
    result = doc.get("result", [])
    for idx, runs in enumerate(result, start=1):
        test_name = f"q{idx}"
        valid = [r for r in runs if _is_valid_time(r)]
        passed = len(valid) == len(runs) and len(valid) > 0

        metrics: list[dict] = []
        if valid:
            metrics.append({
                "name": "min",
                "unit": "s",
                "value": min(valid),
                "direction": "lower_is_better",
            })
            metrics.append({
                "name": "mean",
                "unit": "s",
                "value": sum(valid) / len(valid),
                "direction": "lower_is_better",
            })
            metrics.append({
                "name": "max",
                "unit": "s",
                "value": max(valid),
                "direction": "lower_is_better",
            })

        extra_info = {
            **extras_shared,
            "runs": len(runs),
            "valid_runs": len(valid),
        }

        test: dict = {"test_name": test_name}
        if shared_params:
            test["params"] = dict(shared_params)

        run = dict(run_base)
        run["passed"] = passed

        result_dict: dict = {
            "test": test,
            "run": run,
            "env": env,
            "metrics": metrics,
            "extra_info": extra_info,
        }
        if sut:
            result_dict["sut"] = sut
        out.append(result_dict)

    return out
