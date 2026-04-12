"""Parser for wrk's text output.

wrk's summary format is a fixed-shape text report::

    Running 5s test @ http://localhost:8080/
      2 threads and 10 connections
      Thread Stats   Avg      Stdev     Max   +/- Stdev
        Latency   363.63us  122.95us   5.65ms   97.34%
        Req/Sec    13.95k     0.86k   14.82k    91.18%
      Latency Distribution
         50%  349.00us
         75%  363.00us
         90%  381.00us
         99%  674.00us
      141528 requests in 5.10s, 400.46MB read
    Requests/sec:  27751.65
    Transfer/sec:     78.52MB

All latency values carry a human-readable unit suffix (``us``, ``ms``,
``s``). The parser normalizes to milliseconds for consistency with the
rest of the load-testing parsers.

Per the framework's known-deviation note (see README), wrk produces one
test run, not four — test_name is always ``"homepage"``.

See ``frameworks/loadtest/wrk/README.md``.
"""

from __future__ import annotations

import re


# Unit-bearing duration: "363.63us", "5.65ms", "2.50s"
_DURATION_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*(us|ms|s|m)\s*$")

_TO_MS = {"us": 0.001, "ms": 1.0, "s": 1000.0, "m": 60_000.0}

# "27751.65" or "14.82k" or "1.23M"
_MAG_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([kMG]?)\s*$")
_MAG = {"": 1.0, "k": 1e3, "M": 1e6, "G": 1e9}


def _parse_duration_ms(raw: str) -> float:
    m = _DURATION_RE.match(raw)
    if not m:
        raise ValueError(f"cannot parse wrk duration: {raw!r}")
    return float(m.group(1)) * _TO_MS[m.group(2)]


def _parse_magnitude(raw: str) -> float:
    m = _MAG_RE.match(raw)
    if not m:
        raise ValueError(f"cannot parse wrk magnitude: {raw!r}")
    return float(m.group(1)) * _MAG[m.group(2)]


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    metrics: list[dict] = []

    # Thread Stats Latency: "    Latency   363.63us  122.95us   5.65ms   97.34%"
    m = re.search(r"^\s*Latency\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*$", content, re.MULTILINE)
    if m:
        metrics.append({"name": "latency_avg",    "unit": "ms", "value": _parse_duration_ms(m.group(1)), "direction": "lower_is_better"})
        metrics.append({"name": "latency_stddev", "unit": "ms", "value": _parse_duration_ms(m.group(2)), "direction": "lower_is_better"})
        metrics.append({"name": "latency_max",    "unit": "ms", "value": _parse_duration_ms(m.group(3)), "direction": "lower_is_better"})

    # Latency Distribution: "     50%  349.00us"
    for pct, raw in re.findall(r"^\s*(\d+)%\s+(\S+)\s*$", content, re.MULTILINE):
        metrics.append({
            "name": f"latency_p{pct}",
            "unit": "ms",
            "value": _parse_duration_ms(raw),
            "direction": "lower_is_better",
        })

    # Requests/sec: 27751.65
    m = re.search(r"^Requests/sec:\s*(\S+)\s*$", content, re.MULTILINE)
    if m:
        metrics.append({
            "name": "requests_per_sec",
            "unit": "ops/s",
            "value": _parse_magnitude(m.group(1)),
            "direction": "higher_is_better",
        })

    # Total requests & duration: "  141528 requests in 5.10s, 400.46MB read"
    m = re.search(r"^\s*(\d+)\s+requests\s+in\s+\S+,\s+(\S+)\s+read\s*$", content, re.MULTILINE)
    extra_info: dict = {}
    if m:
        extra_info["total_requests"] = int(m.group(1))
        extra_info["total_read"] = m.group(2)

    # Thread count & connections: "  2 threads and 10 connections"
    m = re.search(r"^\s*(\d+)\s+threads\s+and\s+(\d+)\s+connections\s*$", content, re.MULTILINE)
    if m:
        extra_info["threads"] = int(m.group(1))
        extra_info["connections"] = int(m.group(2))

    result = {
        "timestamp": 0,
        "attributes": {"test_name": "homepage"},
        "metrics": metrics,
        "passed": True,
    }
    if extra_info:
        result["extra_info"] = extra_info
    return [result]
