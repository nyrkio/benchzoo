"""Parser for pytest-benchmark's ``--benchmark-json`` output.

See ``frameworks/language/pytest-benchmark/README.md`` for the parser
notes this implementation follows. In short: each entry in the
top-level ``benchmarks`` array becomes one Nyrkiö JSON test-run dict,
with ``attributes["test_name"]`` derived from ``name`` (``test_``
prefix stripped) and headline metric ``mean`` (seconds, lower is
better).
"""

from __future__ import annotations

import json


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    out: list[dict] = []
    for entry in doc.get("benchmarks", []):
        stats = entry["stats"]

        raw_name = entry["name"]
        test_name = raw_name[len("test_"):] if raw_name.startswith("test_") else raw_name

        metrics = [
            {"name": "mean",   "unit": "s",     "value": stats["mean"],   "direction": "lower_is_better"},
            {"name": "min",    "unit": "s",     "value": stats["min"],    "direction": "lower_is_better"},
            {"name": "max",    "unit": "s",     "value": stats["max"],    "direction": "lower_is_better"},
            {"name": "stddev", "unit": "s",     "value": stats["stddev"], "direction": "lower_is_better"},
            {"name": "median", "unit": "s",     "value": stats["median"], "direction": "lower_is_better"},
            {"name": "ops",    "unit": "ops/s", "value": stats["ops"],    "direction": "higher_is_better"},
        ]

        result = {
            "timestamp": 0,
            "attributes": {"test_name": test_name},
            "metrics": metrics,
            "passed": True,
        }

        group = entry.get("group")
        if group is not None:
            result["extra_info"] = {"group": group}

        out.append(result)

    return out
