"""Parser for Julia BenchmarkTools.jl JSON output.

BenchmarkTools serializes its types in a tagged-JSON format: every
Julia type becomes ``[[<TypeName>], <fields>]``. The top-level shape is::

    [
      {"Julia": "1.11.x", "BenchmarkTools": "1.5.0"},
      [
        ["BenchmarkGroup"],
        [
          {
            "tags": [],
            "data": {
              "benchmark1": [
                ["TrialEstimate"]  (or ["Trial"] depending on save path),
                {
                  "params": [["Parameters"], {...}],
                  "time":        2.15e9,     # nanoseconds
                  "gctime":      0,
                  "memory":      1234,        # bytes
                  "allocs":      5,
                  "times":       [ ...per-sample ns... ]   # for Trial
                }
              ],
              ...
            }
          }
        ]
      ]
    ]

The exact tagged-type varies by which BenchmarkTools save path was
used. ``BenchmarkTools.save`` stores raw Trials (``["Trial"]`` with
a ``times`` array); ``median()`` / ``minimum()`` etc. yield
``["TrialEstimate"]`` with a single ``time``. The parser accepts
both — if ``times`` is present we compute our own stats; otherwise
we use the single ``time`` as the mean.

All times are **nanoseconds**.

See ``frameworks/language/benchmarktools-jl/README.md``.
"""

from __future__ import annotations

import json
import statistics


def _unwrap_tagged(obj):
    """Julia type tags look like ``[type_name, fields]`` — a 2-element
    list with a string tag as the first element. Return (tag, fields)
    or (None, obj) when ``obj`` is not tagged.
    """
    if (
        isinstance(obj, list)
        and len(obj) == 2
        and isinstance(obj[0], str)
    ):
        return obj[0], obj[1]
    return None, obj


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    # Top-level is [metadata_dict, [tagged_group]] — a list of length
    # 2, the second element being a list containing one tagged
    # BenchmarkGroup.
    if not (isinstance(doc, list) and len(doc) >= 2):
        return []
    _meta, payload = doc[0], doc[1]

    # payload is a list of tagged groups; take the first one.
    if not (isinstance(payload, list) and payload):
        return []
    tag, body = _unwrap_tagged(payload[0])
    if not isinstance(body, dict):
        return []

    data = body.get("data", {})

    out: list[dict] = []
    for test_name, tagged in data.items():
        _tag, fields = _unwrap_tagged(tagged)
        if not isinstance(fields, dict):
            continue

        metrics: list[dict] = []
        times = fields.get("times")
        if isinstance(times, list) and times:
            srt = sorted(float(t) for t in times)
            metrics.append({"name": "mean",   "unit": "ns", "value": statistics.fmean(srt), "direction": "lower_is_better"})
            metrics.append({"name": "min",    "unit": "ns", "value": srt[0],                "direction": "lower_is_better"})
            metrics.append({"name": "max",    "unit": "ns", "value": srt[-1],               "direction": "lower_is_better"})
            metrics.append({"name": "median", "unit": "ns", "value": statistics.median(srt),"direction": "lower_is_better"})
            if len(srt) >= 2:
                metrics.append({"name": "stddev", "unit": "ns",
                                "value": statistics.pstdev(srt),
                                "direction": "lower_is_better"})
        elif "time" in fields:
            metrics.append({
                "name": "mean",
                "unit": "ns",
                "value": float(fields["time"]),
                "direction": "lower_is_better",
            })

        extra_info: dict = {}
        if "memory" in fields:
            extra_info["memory_bytes"] = fields["memory"]
        if "allocs" in fields:
            extra_info["allocs"] = fields["allocs"]
        if "gctime" in fields:
            extra_info["gctime_ns"] = fields["gctime"]
        if isinstance(times, list):
            extra_info["samples_count"] = len(times)

        out.append({
            "timestamp": 0,
            "attributes": {"test_name": test_name},
            "metrics": metrics,
            "extra_info": extra_info,
            "passed": True,
        })

    return out
