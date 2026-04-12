"""Parser for Locust's ``--csv=<prefix>`` stats CSV output.

Locust's ``<prefix>_stats.csv`` has 22 columns::

    Type, Name, Request Count, Failure Count,
    Median Response Time, Average Response Time,
    Min Response Time, Max Response Time,
    Average Content Size, Requests/s, Failures/s,
    50%, 66%, 75%, 80%, 90%, 95%, 98%, 99%, 99.9%, 99.99%, 100%

The last row is always ``Type="", Name="Aggregated"`` — a summary
across all requests. We skip the aggregate row and emit one dict per
real request row, with test_name = ``"<Type> <Name>"`` (e.g.
``"GET /"``).

All response times are in **milliseconds** (rounded to integer in
Locust's CSV output — sub-ms loopback requests show as 0 or 1).

See ``frameworks/loadtest/locust/README.md``.
"""

from __future__ import annotations

import csv
import io


# Columns → Nyrkiö metric name.
_LATENCY_COLS = {
    "Median Response Time":  "latency_median",
    "Average Response Time": "latency_avg",
    "Min Response Time":     "latency_min",
    "Max Response Time":     "latency_max",
    "50%":   "latency_p50",
    "66%":   "latency_p66",
    "75%":   "latency_p75",
    "80%":   "latency_p80",
    "90%":   "latency_p90",
    "95%":   "latency_p95",
    "98%":   "latency_p98",
    "99%":   "latency_p99",
    "99.9%": "latency_p999",
    "99.99%":"latency_p9999",
    "100%":  "latency_p100",
}


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    out: list[dict] = []
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        type_ = (row.get("Type") or "").strip()
        name = (row.get("Name") or "").strip()

        if not type_ and name == "Aggregated":
            # Skip the aggregate row — it's a rollup, not a distinct test.
            continue

        test_name = f"{type_} {name}".strip()

        metrics: list[dict] = []
        for col, metric_name in _LATENCY_COLS.items():
            if col in row and row[col]:
                try:
                    metrics.append({
                        "name": metric_name,
                        "unit": "ms",
                        "value": float(row[col]),
                        "direction": "lower_is_better",
                    })
                except ValueError:
                    pass
        if "Requests/s" in row and row["Requests/s"]:
            metrics.append({
                "name": "requests_per_sec",
                "unit": "ops/s",
                "value": float(row["Requests/s"]),
                "direction": "higher_is_better",
            })
        if "Failures/s" in row and row["Failures/s"]:
            metrics.append({
                "name": "failures_per_sec",
                "unit": "ops/s",
                "value": float(row["Failures/s"]),
                "direction": "lower_is_better",
            })

        extra_info: dict = {}
        if "Request Count" in row and row["Request Count"]:
            extra_info["request_count"] = int(row["Request Count"])
        if "Failure Count" in row and row["Failure Count"]:
            extra_info["failure_count"] = int(row["Failure Count"])
        if "Average Content Size" in row and row["Average Content Size"]:
            extra_info["avg_content_size_bytes"] = float(row["Average Content Size"])

        failures = int(row.get("Failure Count") or 0)

        result = {
            "timestamp": 0,
            "attributes": {"test_name": test_name},
            "metrics": metrics,
            "passed": failures == 0,
        }
        if extra_info:
            result["extra_info"] = extra_info
        out.append(result)

    return out
