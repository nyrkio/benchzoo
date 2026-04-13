"""Parser for wrk2's text output.

wrk2's format is a superset of wrk's: the Thread Stats block and
Requests/sec / Transfer/sec trailers are identical, but the latency
distribution section is richer — labeled "Latency Distribution
(HdrHistogram - Recorded Latency)" and containing percentiles with
3-decimal formatting, extending well beyond 99%:

    Latency Distribution (HdrHistogram - Recorded Latency)
     50.000%    0.88ms
     75.000%    1.17ms
     90.000%    1.34ms
     99.000%    1.59ms
     99.900%    1.77ms
     99.990%    2.01ms
     99.999%    2.01ms
    100.000%    2.01ms

Followed optionally by a "Detailed Percentile spectrum:" table (this
parser ignores it — the summary rows are enough).

Latency values use human-readable unit suffixes (``us``, ``ms``,
``s``). Parser normalizes to milliseconds.

test_name is always ``"homepage"`` per the Lighthouse-style
deviation (one test, one endpoint).

See ``frameworks/loadtest/wrk2/README.md``.
"""

from __future__ import annotations

import re


_DURATION_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*(us|ms|s|m)\s*$")
_TO_MS = {"us": 0.001, "ms": 1.0, "s": 1000.0, "m": 60_000.0}
_MAG_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([kMG]?)\s*$")
_MAG = {"": 1.0, "k": 1e3, "M": 1e6, "G": 1e9}


def _parse_duration_ms(raw: str) -> float:
    m = _DURATION_RE.match(raw)
    if not m:
        raise ValueError(f"cannot parse wrk2 duration: {raw!r}")
    return float(m.group(1)) * _TO_MS[m.group(2)]


def _parse_magnitude(raw: str) -> float:
    m = _MAG_RE.match(raw)
    if not m:
        raise ValueError(f"cannot parse wrk2 magnitude: {raw!r}")
    return float(m.group(1)) * _MAG[m.group(2)]


def _pct_to_name(pct_raw: str) -> str:
    """'50.000' → 'p50', '99.999' → 'p99999', '100.000' → 'p100'."""
    # Strip trailing zeros after decimal, collapse to integer-like id.
    pct = pct_raw.rstrip("0").rstrip(".")
    return "latency_p" + pct.replace(".", "")


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    metrics: list[dict] = []

    # Thread Stats Latency: "Latency    0.89ms  358.56us   2.01ms   66.07%"
    m = re.search(
        r"^\s*Latency\s+(\S+)\s+(\S+)\s+(\S+)\s+\S+\s*$",
        content, re.MULTILINE,
    )
    if m:
        metrics.append({"name": "latency_avg",    "unit": "ms", "value": _parse_duration_ms(m.group(1)), "direction": "lower_is_better"})
        metrics.append({"name": "latency_stddev", "unit": "ms", "value": _parse_duration_ms(m.group(2)), "direction": "lower_is_better"})
        metrics.append({"name": "latency_max",    "unit": "ms", "value": _parse_duration_ms(m.group(3)), "direction": "lower_is_better"})

    # HdrHistogram rows: " 50.000%    0.88ms"
    # Stop scanning once the "Detailed Percentile spectrum" section begins.
    lines = content.splitlines()
    in_percentiles = False
    for line in lines:
        if line.strip().startswith("Latency Distribution"):
            in_percentiles = True
            continue
        if "Detailed Percentile" in line:
            break
        if not in_percentiles:
            continue
        m = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)%\s+(\S+)\s*$", line)
        if m:
            try:
                metrics.append({
                    "name": _pct_to_name(m.group(1)),
                    "unit": "ms",
                    "value": _parse_duration_ms(m.group(2)),
                    "direction": "lower_is_better",
                })
            except ValueError:
                pass

    # Requests/sec: 998.43
    m = re.search(r"^Requests/sec:\s*(\S+)\s*$", content, re.MULTILINE)
    if m and m.group(1) not in ("-nan", "nan"):
        try:
            metrics.append({
                "name": "requests_per_sec",
                "unit": "ops/s",
                "value": _parse_magnitude(m.group(1)),
                "direction": "higher_is_better",
            })
        except ValueError:
            pass

    extra_info: dict = {}
    m = re.search(r"^\s*(\d+)\s+requests\s+in\s+\S+,\s+(\S+)\s+read\s*$",
                  content, re.MULTILINE)
    if m:
        extra_info["total_requests"] = int(m.group(1))
        extra_info["total_read"] = m.group(2)

    result = {
        "timestamp": 0,
        "attributes": {"test_name": "homepage"},
        "metrics": metrics,
        "passed": True,
    }
    if extra_info:
        result["extra_info"] = extra_info
    return [result]
