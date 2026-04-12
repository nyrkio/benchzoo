"""Parser for vegeta's ``report -type=json`` output.

vegeta's JSON report is a single top-level object::

    {
      "latencies": {"total": ..., "mean": 229296, "50th": 213043,
                    "90th": ..., "95th": ..., "99th": ...,
                    "max": ..., "min": ...},        # all in NANOSECONDS
      "bytes_in":  {"total": 1374500, "mean": 2749},
      "bytes_out": {"total": 0,       "mean": 0},
      "earliest": "2026-04-12T...",                 # RFC 3339 — DO NOT use for timestamp
      "latest":   "2026-04-12T...",
      "end":      "2026-04-12T...",
      "duration": 4990545595,                        # nanoseconds
      "wait":     287783,
      "requests": 500,
      "rate":     100.18,                            # requests/sec achieved
      "throughput": 100.18,                          # successful requests/sec
      "success":  1,                                 # 0.0–1.0 ratio
      "status_codes": {"200": 500},
      "errors": []
    }

Per the framework's known-deviation note, vegeta runs one attack,
producing one test_name = ``"homepage"``.

Latency fields are normalized from nanoseconds to milliseconds for
cross-parser consistency. ``earliest``/``latest``/``end`` are
wall-clock timestamps and MUST NOT be used for Nyrkiö ``timestamp``.

See ``frameworks/loadtest/vegeta/README.md``.
"""

from __future__ import annotations

import json


_NS_TO_MS = 1e-6


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    lat = doc.get("latencies", {})
    metrics: list[dict] = []

    for json_key, metric_name in [
        ("mean", "latency_mean"),
        ("min",  "latency_min"),
        ("max",  "latency_max"),
        ("50th", "latency_p50"),
        ("90th", "latency_p90"),
        ("95th", "latency_p95"),
        ("99th", "latency_p99"),
    ]:
        if json_key in lat:
            metrics.append({
                "name": metric_name,
                "unit": "ms",
                "value": lat[json_key] * _NS_TO_MS,
                "direction": "lower_is_better",
            })

    if "rate" in doc:
        metrics.append({
            "name": "rate",
            "unit": "ops/s",
            "value": doc["rate"],
            "direction": "higher_is_better",
        })
    if "throughput" in doc:
        metrics.append({
            "name": "throughput",
            "unit": "ops/s",
            "value": doc["throughput"],
            "direction": "higher_is_better",
        })
    if "success" in doc:
        metrics.append({
            "name": "success_ratio",
            "unit": "",
            "value": doc["success"],
            "direction": "higher_is_better",
        })

    extra_info = {
        "requests": doc.get("requests", 0),
        "status_codes": doc.get("status_codes", {}),
    }
    if doc.get("errors"):
        extra_info["errors"] = doc["errors"]

    return [{
        "timestamp": 0,
        "attributes": {"test_name": "homepage"},
        "metrics": metrics,
        "extra_info": extra_info,
        # vegeta's success field is fractional; parser contract is boolean.
        # 100% success → passed; any failure → passed=False.
        "passed": doc.get("success", 1) == 1,
    }]
