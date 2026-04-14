"""Parser for the generic CSV escape-hatch format.

Input is a header row ``test_name,metric_name,unit,value,direction``
followed by one data row per (test, metric) pair. Rows with the same
``test_name`` are grouped into one Nyrkiö dict with multiple metrics.
Empty ``unit`` / ``direction`` fields mean the corresponding key is
omitted on that metric (not set to an empty string or ``null``).

See ``frameworks/generic/custom-csv/README.md`` for the format spec.
"""

from __future__ import annotations

import csv
import io


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    reader = csv.DictReader(io.StringIO(content))

    by_test: dict[str, dict] = {}
    order: list[str] = []

    for row in reader:
        test_name = row["test_name"]
        if not test_name:
            # Ignore blank lines / rows without a test name.
            continue

        metric: dict = {
            "name": row["metric_name"],
            "value": float(row["value"]),
        }
        unit = row.get("unit") or ""
        if unit:
            metric["unit"] = unit
        direction = row.get("direction") or ""
        if direction:
            metric["direction"] = direction

        if test_name not in by_test:
            by_test[test_name] = {
                "test": {"test_name": test_name},
                "run": {"passed": True},
                "env": {"framework": {"name": "custom-csv"}},
                "metrics": [],
            }
            order.append(test_name)
        by_test[test_name]["metrics"].append(metric)

    return [by_test[name] for name in order]
