"""Parser for mitata's JSON output.

mitata 1.x doesn't produce a pure-JSON stdout even with
``run({json: true})`` — it prints its pretty ANSI table first and
then returns a JSON-friendly object, which our ``sample-benchmark.js``
stringifies after the table. Captured output.json therefore looks
like::

    <ANSI-decorated pretty table>
    <blank>
    {
      "framework": "mitata",
      "version": "1.0.34",
      "month": 4,
      "results": {
        "benchmarks": [
          {
            "alias": "benchmark1",
            "runs": [{
              "stats": {
                "samples": [ ... ns ... ],
                "min":  2149222974, "max":  2153375925,
                "p25":  2150509100, "p50":  2152415567,
                "p75":  2152614543, "p99":  2153127173,
                "p999": 2153127173, "avg":  2151865164.83,
                "ticks": 12,
                "heap": { "_": 4, "total": ..., "min": ..., "max": ..., "avg": ... }
              },
              "name": "benchmark1"
            }]
          },
          ...
        ]
      }
    }

All timing values are in **nanoseconds**. We emit them as unit ``"ns"``.

test_name comes from ``benchmarks[i].alias`` (or ``runs[0].name`` if
``alias`` is absent). Samples arrays are kept out of ``extra_info``;
only the count is preserved via ``samples_count``.

See ``frameworks/language/mitata/README.md``.
"""

from __future__ import annotations

import json
import re


# Strip ANSI escape codes (mitata's pretty table colors its output
# even when piped).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _extract_json_envelope(text: str) -> dict:
    """Find the trailing JSON object in mitata's mixed output."""
    # mitata prints the pretty table first, then our JSON.stringify
    # output. The JSON envelope starts with the first '{' that
    # appears at column 0 of a line after the table ends.
    stripped = _ANSI_RE.sub("", text)
    # Find the last top-level '{' that starts a well-formed JSON object
    # by scanning from each '{' until one parses.
    for idx in range(len(stripped)):
        if stripped[idx] != "{":
            continue
        try:
            return json.loads(stripped[idx:])
        except json.JSONDecodeError:
            continue
    raise RuntimeError("mitata output has no parseable JSON envelope")


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    doc = _extract_json_envelope(content)

    out: list[dict] = []
    results = doc.get("results", {})
    benchmarks = results.get("benchmarks", []) if isinstance(results, dict) else []

    for bench in benchmarks:
        if not isinstance(bench, dict):
            continue
        runs = bench.get("runs") or []
        if not runs or not isinstance(runs[0], dict):
            continue
        run = runs[0]
        stats = run.get("stats") or {}

        test_name = bench.get("alias") or run.get("name") or ""
        if not test_name:
            continue

        metrics: list[dict] = []
        for key, metric_name in [
            ("avg", "mean"),
            ("min", "min"),
            ("max", "max"),
            ("p25", "p25"),
            ("p50", "p50"),
            ("p75", "p75"),
            ("p99", "p99"),
            ("p999", "p999"),
        ]:
            if key in stats and isinstance(stats[key], (int, float)):
                metrics.append({
                    "name": metric_name,
                    "unit": "ns",
                    "value": stats[key],
                    "direction": "lower_is_better",
                })

        extra_info: dict = {}
        samples = stats.get("samples")
        if isinstance(samples, list):
            extra_info["samples_count"] = len(samples)
        if "ticks" in stats:
            extra_info["ticks"] = stats["ticks"]

        out.append({
            "timestamp": 0,
            "attributes": {"test_name": test_name},
            "metrics": metrics,
            "extra_info": extra_info,
            "passed": True,
        })

    return out
