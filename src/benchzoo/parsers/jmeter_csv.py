"""Parser for Apache JMeter's per-sample CSV output.

JMeter's CSV (written via ``-l <file>`` in non-GUI mode) is unlike
most load-tester outputs: it is **one row per request**, not
pre-aggregated stats. Header::

    timeStamp,elapsed,label,responseCode,responseMessage,threadName,
    dataType,success,failureMessage,bytes,sentBytes,grpThreads,
    allThreads,URL,Latency,IdleTime,Connect

The parser therefore aggregates per ``label`` (one Nyrkiö dict per
distinct label, with computed mean/median/p50/p90/p95/p99 across
the label's rows).

All timings are in **milliseconds**. ``elapsed`` is end-to-end
response time; ``Latency`` is time-to-first-byte; ``Connect`` is TCP
connect time.

See ``frameworks/loadtest/jmeter/README.md``.
"""

from __future__ import annotations

import csv
import io
import statistics


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    # Nearest-rank method — matches JMeter's own summary reporter.
    idx = max(0, min(len(sorted_values) - 1,
                     int(round(pct / 100.0 * (len(sorted_values) - 1)))))
    return sorted_values[idx]


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    # Group rows by label.
    groups: dict[str, dict[str, list[float]]] = {}
    failures: dict[str, int] = {}
    counts: dict[str, int] = {}

    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        label = row.get("label", "").strip()
        if not label:
            continue
        groups.setdefault(label, {"elapsed": [], "latency": [], "connect": []})
        try:
            groups[label]["elapsed"].append(float(row["elapsed"]))
            groups[label]["latency"].append(float(row.get("Latency", 0) or 0))
            groups[label]["connect"].append(float(row.get("Connect", 0) or 0))
        except ValueError:
            continue
        counts[label] = counts.get(label, 0) + 1
        if row.get("success", "").strip().lower() != "true":
            failures[label] = failures.get(label, 0) + 1

    out: list[dict] = []
    for label, series in groups.items():
        elapsed = sorted(series["elapsed"])
        if not elapsed:
            continue

        metrics = [
            {"name": "elapsed_mean",   "unit": "ms", "value": statistics.fmean(elapsed),              "direction": "lower_is_better"},
            {"name": "elapsed_median", "unit": "ms", "value": statistics.median(elapsed),             "direction": "lower_is_better"},
            {"name": "elapsed_min",    "unit": "ms", "value": min(elapsed),                           "direction": "lower_is_better"},
            {"name": "elapsed_max",    "unit": "ms", "value": max(elapsed),                           "direction": "lower_is_better"},
            {"name": "elapsed_p90",    "unit": "ms", "value": _percentile(elapsed, 90),               "direction": "lower_is_better"},
            {"name": "elapsed_p95",    "unit": "ms", "value": _percentile(elapsed, 95),               "direction": "lower_is_better"},
            {"name": "elapsed_p99",    "unit": "ms", "value": _percentile(elapsed, 99),               "direction": "lower_is_better"},
        ]
        latency = sorted(series["latency"])
        if latency:
            metrics.append({"name": "latency_mean", "unit": "ms",
                            "value": statistics.fmean(latency),
                            "direction": "lower_is_better"})
        connect = sorted(series["connect"])
        if connect:
            metrics.append({"name": "connect_mean", "unit": "ms",
                            "value": statistics.fmean(connect),
                            "direction": "lower_is_better"})

        extra_info = {
            "samples": counts[label],
            "failures": failures.get(label, 0),
        }

        out.append({
            "test": {"test_name": label},
            "run": {"passed": failures.get(label, 0) == 0},
            "env": {"framework": {"name": "jmeter"}},
            "metrics": metrics,
            "extra_info": extra_info,
        })

    return out
