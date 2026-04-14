"""Parser for hyperfine's ``--export-csv`` output.

hyperfine's CSV format is a flat table with header row::

    command,mean,stddev,median,user,system,min,max
    benchmark1,2.15296...,6.49e-05,2.15298...,0.00119914,0.00173575,2.15283...,2.15304...

All durations are in **seconds** (same as the JSON export). Compared to
the JSON export, the CSV format loses:

- ``times`` (the per-run wall times) — only aggregate stats are present.
- ``exit_codes`` — no way to detect failed runs. The CSV parser
  therefore always sets ``passed: True``; if any run failed, this is a
  silent loss of information and a reason to prefer the JSON format
  when available.

See ``frameworks/generic/hyperfine/README.md``.
"""

from __future__ import annotations

import csv
import io


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    out: list[dict] = []
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        metrics = [
            {"name": "mean",   "unit": "s", "value": float(row["mean"]),   "direction": "lower_is_better"},
            {"name": "stddev", "unit": "s", "value": float(row["stddev"]), "direction": "lower_is_better"},
            {"name": "median", "unit": "s", "value": float(row["median"]), "direction": "lower_is_better"},
            {"name": "min",    "unit": "s", "value": float(row["min"]),    "direction": "lower_is_better"},
            {"name": "max",    "unit": "s", "value": float(row["max"]),    "direction": "lower_is_better"},
            {"name": "user",   "unit": "s", "value": float(row["user"]),   "direction": "lower_is_better"},
            {"name": "system", "unit": "s", "value": float(row["system"]), "direction": "lower_is_better"},
        ]
        out.append({
            "test": {"test_name": row["command"]},
            "run": {"passed": True},  # CSV lacks exit_codes — see module docstring.
            "env": {"framework": {"name": "hyperfine"}},
            "metrics": metrics,
        })

    return out
