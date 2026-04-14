"""Parser for redis-benchmark's ``--csv`` output.

Redis 7 emits an 8-column CSV with a header row::

    "test","rps","avg_latency_ms","min_latency_ms","p50_latency_ms",
    "p95_latency_ms","p99_latency_ms","max_latency_ms"
    "SET","26567.48","1.550","0.088","1.415","2.911","3.959","10.911"
    "GET","28011.21","1.509","0.080","1.391","2.759","3.999","14.831"
    ...

Older Redis versions emitted fewer columns (≤6.0: test+rps only; 6.2
added avg_latency_ms). The parser keys by header name to handle any
version.

Each row becomes one Nyrkiö dict with ``test_name`` = the command
(e.g. "SET"). Since redis-benchmark runs several commands in one
invocation, the parser typically returns multiple dicts.

See ``frameworks/database/redis-benchmark/README.md``.
"""

from __future__ import annotations

import csv
import io


# Map the CSV column → (metric_name, direction).
# "rps" is higher_is_better; all latency columns are lower_is_better.
_LATENCY_COLS = {
    "avg_latency_ms":  "avg_latency",
    "min_latency_ms":  "min_latency",
    "p50_latency_ms":  "p50_latency",
    "p95_latency_ms":  "p95_latency",
    "p99_latency_ms":  "p99_latency",
    "max_latency_ms":  "max_latency",
}


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    out: list[dict] = []
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        test = row.get("test", "").strip()
        if not test:
            continue

        metrics: list[dict] = []
        if "rps" in row and row["rps"]:
            metrics.append({
                "name": "rps",
                "unit": "ops/s",
                "value": float(row["rps"]),
                "direction": "higher_is_better",
            })
        for col, metric_name in _LATENCY_COLS.items():
            if col in row and row[col]:
                metrics.append({
                    "name": metric_name,
                    "unit": "ms",
                    "value": float(row[col]),
                    "direction": "lower_is_better",
                })

        out.append({
            "test": {"test_name": test},
            "run": {"passed": True},
            "env": {"framework": {"name": "redis-benchmark"}},
            "metrics": metrics,
        })

    return out
