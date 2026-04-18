"""Parser for Google Benchmark's ``--benchmark_out_format=csv`` output.

The CSV output is a flat table. Google Benchmark first prints a
few human-readable header lines (``Run on (...)``, ``CPU Caches:`` etc.)
and *then* the CSV itself, starting with the line::

    name,iterations,real_time,cpu_time,time_unit,bytes_per_second,items_per_second,label,error_occurred,error_message

Each subsequent row is one benchmark result. A failed benchmark has
``error_occurred`` set to a truthy value and an ``error_message``.

See ``frameworks/language/google-benchmark/README.md`` for the parser
notes this implementation follows.
"""

from __future__ import annotations

import csv
import io

from ._google_benchmark_common import split_benchmark_name


_HEADER_PREFIX = "name,iterations,real_time,cpu_time,time_unit"


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    # Google Benchmark prefixes the CSV with free-text lines; skip until
    # we hit the real header row.
    lines = content.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith(_HEADER_PREFIX):
            start = i
            break
    if start is None:
        return []

    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))

    out: list[dict] = []
    for row in reader:
        raw_name = row.get("name", "").strip()
        if not raw_name:
            continue
        # Split the configured parameters (args, threads, iterations)
        # out of the composite name — see google_benchmark_json.py for
        # the full rationale.
        name, name_attrs = split_benchmark_name(raw_name)
        unit = row.get("time_unit") or "ns"

        try:
            real_time = float(row["real_time"])
            cpu_time = float(row["cpu_time"])
        except (KeyError, ValueError):
            continue

        metrics = [
            {
                "name": "real_time",
                "unit": unit,
                "value": real_time,
                "direction": "lower_is_better",
            },
            {
                "name": "cpu_time",
                "unit": unit,
                "value": cpu_time,
                "direction": "lower_is_better",
            },
        ]

        err = (row.get("error_occurred") or "").strip().lower()
        passed = err in ("", "false", "0")

        test_block: dict = {"test_name": name}
        if name_attrs:
            test_block["params"] = name_attrs
        out.append({
            "test": test_block,
            "run": {"passed": passed},
            "env": {"framework": {"name": "google-benchmark"}},
            "metrics": metrics,
        })

    return out
