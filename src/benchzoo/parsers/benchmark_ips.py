"""Parser for benchmark-ips's custom JSON output.

benchmark-ips (the Ruby benchmarking library) has no stable built-in
JSON reporter, so our sample-benchmark.js emits a self-defined
envelope wrapping each ``Benchmark::IPS::Report::Entry``::

    {
      "benchmark_ips_version": "2.14.0",
      "ruby_version": "3.3.x",
      "month_utc": 4,
      "benchmarks": [
        {
          "name": "benchmark1",
          "ips": 0.4650,
          "ips_stddev": 0,
          "microseconds_per_iteration": 2150128.3,
          "seconds_per_iteration": 2.1501,
          "iterations": 1,
          "measurement_cycle": 1,
          "stats_class": "Benchmark::IPS::Stats::SD"
        },
        ...
      ]
    }

We emit **both** the natural benchmark-ips metric (``ips`` = iterations
per second, ``higher_is_better``) and its reciprocal ``mean`` in
seconds (``lower_is_better``) so ground-truth assertions against the
canonical 2.15 s sleep work naturally. ``ips_stddev`` exposed as
``stddev_ips``.

See ``frameworks/language/benchmark-ips/README.md``.
"""

from __future__ import annotations

import json


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    framework: dict = {"name": "benchmark-ips"}
    if doc.get("benchmark_ips_version"):
        framework["version"] = doc["benchmark_ips_version"]

    env: dict = {"framework": framework}
    if doc.get("ruby_version"):
        env["runtime"] = f"ruby {doc['ruby_version']}"

    out: list[dict] = []
    for entry in doc.get("benchmarks", []):
        name = entry.get("name", "").strip()
        if not name:
            continue

        ips = float(entry.get("ips") or 0)
        seconds_per_iter = float(entry.get("seconds_per_iteration") or 0)

        metrics = [
            {"name": "ips",        "unit": "ops/s", "value": ips,                "direction": "higher_is_better"},
            {"name": "mean",       "unit": "s",     "value": seconds_per_iter,   "direction": "lower_is_better"},
            {"name": "stddev_ips", "unit": "ops/s", "value": float(entry.get("ips_stddev") or 0)},
        ]

        extra_info: dict = {
            "iterations": entry.get("iterations", 0),
            "measurement_cycle": entry.get("measurement_cycle", 0),
        }
        if entry.get("stats_class"):
            extra_info["stats_class"] = entry["stats_class"]

        out.append({
            "test": {"test_name": name},
            "run": {"passed": True},
            "env": env,
            "metrics": metrics,
            "extra_info": extra_info,
        })

    return out
