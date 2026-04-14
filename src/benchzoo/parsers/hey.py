"""Parser for hey's text output.

hey (https://github.com/rakyll/hey) emits a plain-text summary::

    Summary:
      Total:        5.0016 secs
      Slowest:      0.0080 secs
      Fastest:      0.0001 secs
      Average:      0.0005 secs
      Requests/sec: 19887.0008

      Total data:    293225768 bytes
      Size/request:  2948 bytes

    Response time histogram:
      0.000 [1]     |
      ...

    Latency distribution:
      10% in 0.0001 secs
      ...
      99% in 0.0027 secs

    Details (average, fastest, slowest):
      DNS+dialup:   0.0000 secs, 0.0001 secs, 0.0080 secs
      ...

All timings are in **seconds** (hey's native unit — unlike wrk's
scaled us/ms). The parser normalizes to milliseconds for consistency
with other load-test parsers in the corpus.

Per the framework's known-deviation note, hey produces one test run,
not four — test_name is always ``"homepage"``.

See ``frameworks/loadtest/hey/README.md``.
"""

from __future__ import annotations

import re


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    metrics: list[dict] = []

    # Summary block: "Average: 0.0005 secs", "Requests/sec: 19887.0008"
    def _summary_secs(label: str) -> float | None:
        m = re.search(rf"^\s*{label}:\s+([0-9.]+)\s+secs\s*$", content, re.MULTILINE)
        return float(m.group(1)) if m else None

    for name, label in [
        ("latency_total", "Total"),
        ("latency_slowest", "Slowest"),
        ("latency_fastest", "Fastest"),
        ("latency_avg", "Average"),
    ]:
        secs = _summary_secs(label)
        if secs is not None:
            metrics.append({
                "name": name,
                "unit": "ms",
                "value": secs * 1000.0,
                "direction": "lower_is_better",
            })

    m = re.search(r"^\s*Requests/sec:\s+([0-9.]+)\s*$", content, re.MULTILINE)
    if m:
        metrics.append({
            "name": "requests_per_sec",
            "unit": "ops/s",
            "value": float(m.group(1)),
            "direction": "higher_is_better",
        })

    # Latency distribution: "  50% in 0.0003 secs"
    for pct, secs in re.findall(
        r"^\s*(\d+)%\s+in\s+([0-9.]+)\s+secs\s*$", content, re.MULTILINE
    ):
        metrics.append({
            "name": f"latency_p{pct}",
            "unit": "ms",
            "value": float(secs) * 1000.0,
            "direction": "lower_is_better",
        })

    extra_info: dict = {}
    m = re.search(r"^\s*Total data:\s+(\d+)\s+bytes\s*$", content, re.MULTILINE)
    if m:
        extra_info["total_data_bytes"] = int(m.group(1))
    m = re.search(r"^\s*Size/request:\s+(\d+)\s+bytes\s*$", content, re.MULTILINE)
    if m:
        extra_info["size_per_request_bytes"] = int(m.group(1))

    result = {
        "test": {"test_name": "homepage"},
        "run": {"passed": True},
        "env": {"framework": {"name": "hey"}},
        "metrics": metrics,
    }
    if extra_info:
        result["extra_info"] = extra_info
    return [result]
