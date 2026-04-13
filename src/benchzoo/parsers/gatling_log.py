"""Parser for Gatling's simulation.log text output.

Each line starts with a type marker (``RUN``, ``USER``, ``REQUEST``)
followed by tab-separated fields. Only ``REQUEST`` lines carry
timing data::

    REQUEST\t<scenario>\t<request_name>\t<start_ts>\t<end_ts>\t<status>\t[<error>]

Timestamps are epoch milliseconds; latency = end_ts - start_ts.
Status is ``OK`` or ``KO``.

Gatling's simulation.log field count has shifted across minor
versions (3.7 had a user-id column, 3.10+ dropped it). We parse by
locating the two integer timestamps in each row — robust against
column-shift churn. Status is always the field right after the
second timestamp.

Parser aggregates per distinct ``request_name`` into a single Nyrkiö
dict per test_name, with mean/median/p50/p90/p95/p99/max and
success rate.

See ``frameworks/loadtest/gatling/README.md``.
"""

from __future__ import annotations

import statistics


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    idx = max(0, min(len(sorted_values) - 1,
                     int(round(pct / 100.0 * (len(sorted_values) - 1)))))
    return sorted_values[idx]


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    groups: dict[str, list[float]] = {}
    failures: dict[str, int] = {}
    counts: dict[str, int] = {}

    for line in content.splitlines():
        if not line.startswith("REQUEST"):
            continue
        fields = line.split("\t")
        if len(fields) < 6:
            continue
        # Find two consecutive integers (start_ts, end_ts). This is
        # robust to Gatling's column-count variations across versions.
        ts_positions = []
        for i, f in enumerate(fields):
            s = f.strip()
            if s.isdigit() and len(s) >= 10:   # looks like a ms epoch ts
                ts_positions.append((i, int(s)))
        if len(ts_positions) < 2:
            continue
        (i1, start_ts), (i2, end_ts) = ts_positions[0], ts_positions[1]
        if i2 - i1 != 1:
            continue
        latency_ms = end_ts - start_ts

        status = fields[i2 + 1].strip() if i2 + 1 < len(fields) else "OK"
        # request_name is the last non-empty field before the first timestamp.
        name_candidates = [f.strip() for f in fields[:i1] if f.strip()]
        if not name_candidates:
            continue
        request_name = name_candidates[-1]

        groups.setdefault(request_name, []).append(float(latency_ms))
        counts[request_name] = counts.get(request_name, 0) + 1
        if status != "OK":
            failures[request_name] = failures.get(request_name, 0) + 1

    out: list[dict] = []
    for name, latencies in groups.items():
        if not latencies:
            continue
        srt = sorted(latencies)
        metrics = [
            {"name": "latency_mean",   "unit": "ms", "value": statistics.fmean(srt),          "direction": "lower_is_better"},
            {"name": "latency_median", "unit": "ms", "value": statistics.median(srt),         "direction": "lower_is_better"},
            {"name": "latency_min",    "unit": "ms", "value": min(srt),                        "direction": "lower_is_better"},
            {"name": "latency_max",    "unit": "ms", "value": max(srt),                        "direction": "lower_is_better"},
            {"name": "latency_p90",    "unit": "ms", "value": _percentile(srt, 90),            "direction": "lower_is_better"},
            {"name": "latency_p95",    "unit": "ms", "value": _percentile(srt, 95),            "direction": "lower_is_better"},
            {"name": "latency_p99",    "unit": "ms", "value": _percentile(srt, 99),            "direction": "lower_is_better"},
        ]
        out.append({
            "timestamp": 0,
            "attributes": {"test_name": name},
            "metrics": metrics,
            "extra_info": {
                "samples": counts[name],
                "failures": failures.get(name, 0),
            },
            "passed": failures.get(name, 0) == 0,
        })

    return out
