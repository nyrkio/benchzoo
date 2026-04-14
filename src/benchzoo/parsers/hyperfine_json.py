"""Parser for hyperfine's ``--export-json`` output.

Emits the **v2 schema** (see ``docs/schema-v2.md``). hyperfine's JSON
carries a minimal amount of metadata (command, stats, per-run times,
exit codes) and no commit/env context — making it a good minimal-case
counterpart to pytest-benchmark's richness.
"""

from __future__ import annotations

import json


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    out: list[dict] = []
    for entry in doc.get("results", []):
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
            "test": {"test_name": entry["command"]},
            "run": {"passed": passed},
            "env": {"framework": {"name": "hyperfine"}},
            "metrics": metrics,
        })

    return out
