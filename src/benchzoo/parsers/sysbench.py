"""Parser for sysbench text output.

sysbench emits a plain-text report per invocation with a ``General
statistics`` block and a ``Latency (ms)`` block. benchzoo's corpus
runs sysbench four separate times (once per ``benchmarkN.lua``) and
``run.sh`` concatenates the outputs with ``=== benchmarkN ===``
separator lines.

A single block looks roughly like::

    General statistics:
        total time:                          2.1528s
        total number of events:              1

    Latency (ms):
             min:                                 2152.61
             avg:                                 2152.61
             max:                                 2152.61
             95th percentile:                     2159.29
             sum:                                 2152.61

See ``frameworks/database/sysbench/README.md`` for the parser notes
this implementation follows.
"""

from __future__ import annotations

import re


_SEPARATOR_RE = re.compile(r"^===\s*(\S+)\s*===\s*$", re.MULTILINE)

_TOTAL_TIME_RE = re.compile(r"^\s*total time:\s*([0-9.]+)\s*s\s*$", re.MULTILINE)
_TOTAL_EVENTS_RE = re.compile(
    r"^\s*total number of events:\s*(\d+)\s*$", re.MULTILINE
)

_LAT_MIN_RE = re.compile(r"^\s*min:\s*([0-9.]+)\s*$", re.MULTILINE)
_LAT_AVG_RE = re.compile(r"^\s*avg:\s*([0-9.]+)\s*$", re.MULTILINE)
_LAT_MAX_RE = re.compile(r"^\s*max:\s*([0-9.]+)\s*$", re.MULTILINE)
_LAT_P95_RE = re.compile(r"^\s*95th percentile:\s*([0-9.]+)\s*$", re.MULTILINE)
_LAT_SUM_RE = re.compile(r"^\s*sum:\s*([0-9.]+)\s*$", re.MULTILINE)


def _split_blocks(text: str) -> list[tuple[str, str]]:
    matches = list(_SEPARATOR_RE.finditer(text))
    blocks: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks.append((m.group(1), text[start:end]))
    return blocks


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    out: list[dict] = []
    for marker_name, block in _split_blocks(content):
        metrics: list[dict] = []

        for name, regex in (
            ("latency_min", _LAT_MIN_RE),
            ("latency_avg", _LAT_AVG_RE),
            ("latency_max", _LAT_MAX_RE),
            ("latency_p95", _LAT_P95_RE),
            ("latency_sum", _LAT_SUM_RE),
        ):
            m = regex.search(block)
            if m:
                metrics.append({
                    "name": name,
                    "unit": "ms",
                    "value": float(m.group(1)),
                    "direction": "lower_is_better",
                })

        m = _TOTAL_TIME_RE.search(block)
        if m:
            metrics.append({
                "name": "total_time",
                "unit": "s",
                "value": float(m.group(1)),
                "direction": "lower_is_better",
            })

        extra_info: dict = {}
        m = _TOTAL_EVENTS_RE.search(block)
        if m:
            extra_info["number_of_events"] = int(m.group(1))

        result: dict = {
            "timestamp": 0,
            "attributes": {"test_name": marker_name},
            "metrics": metrics,
            "passed": True,
        }
        if extra_info:
            result["extra_info"] = extra_info
        out.append(result)

    return out
