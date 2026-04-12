"""Parser for hyperfine's ``--export-json`` output.

hyperfine's JSON format is a single object with a top-level ``results``
array. Each entry in ``results`` is one benchmarked command, shaped
roughly like::

    {
      "command": "benchmark1",            # our --command-name, else raw shell
      "mean":    2.1529678312,            # seconds
      "stddev":  0.00006490665,           # seconds
      "median":  2.1529894792,            # seconds
      "user":    0.00119914,              # CPU time in user mode, seconds
      "system":  0.00173575,              # CPU time in kernel mode, seconds
      "min":     2.1528362427,            # seconds
      "max":     2.1530476307,            # seconds
      "times":   [ ... per-run wall times, seconds ... ],
      "exit_codes": [ 0, 0, 0, ... ]
    }

All reported durations are in **seconds** (float). ``times`` and
``exit_codes`` are parallel arrays of the individual runs.

See ``frameworks/generic/hyperfine/README.md`` for the parser notes
this implementation follows.
"""

from __future__ import annotations

import json


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    out: list[dict] = []
    for entry in doc.get("results", []):
        # Every run's exit code is 0 iff the command never failed.
        exit_codes = entry.get("exit_codes", [])
        passed = all(code == 0 for code in exit_codes) if exit_codes else True

        metrics = [
            {"name": "mean",   "unit": "s", "value": entry["mean"],   "direction": "lower_is_better"},
            {"name": "stddev", "unit": "s", "value": entry["stddev"], "direction": "lower_is_better"},
            {"name": "median", "unit": "s", "value": entry["median"], "direction": "lower_is_better"},
            {"name": "min",    "unit": "s", "value": entry["min"],    "direction": "lower_is_better"},
            {"name": "max",    "unit": "s", "value": entry["max"],    "direction": "lower_is_better"},
            {"name": "user",   "unit": "s", "value": entry["user"],   "direction": "lower_is_better"},
            {"name": "system", "unit": "s", "value": entry["system"], "direction": "lower_is_better"},
        ]

        out.append({
            "timestamp": 0,
            "attributes": {"test_name": entry["command"]},
            "metrics": metrics,
            "passed": passed,
        })

    return out
