"""Parser for Google Benchmark's ``--benchmark_out_format=json`` output.

Google Benchmark emits a top-level object with two keys:

- ``context`` — host info (CPU model, caches, ``num_cpus``), library
  metadata, and a wall-clock ``date`` field.
- ``benchmarks`` — an array of per-benchmark result entries.

Each entry in ``benchmarks`` carries at least ``name`` / ``run_name``,
``iterations``, ``real_time``, ``cpu_time``, and ``time_unit`` (one of
``"ns"``, ``"us"``, ``"ms"``, ``"s"``). A failed benchmark is signalled
by ``"error_occurred": true`` plus an ``"error_message"`` string.

``context.date`` is a wall-clock timestamp and is **not** used for the
Nyrkiö ``timestamp`` field — per ``docs/design.md`` that field is
git-derived and parsers always set it to ``0``.

See ``frameworks/language/google-benchmark/README.md`` for the parser
notes this implementation follows.
"""

from __future__ import annotations

import json


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    out: list[dict] = []
    for entry in doc.get("benchmarks", []):
        # Skip aggregate rows produced by ->Repetitions() — they repeat
        # the underlying iterations and would double-count.
        if entry.get("run_type") == "aggregate":
            continue

        test_name = entry.get("run_name") or entry.get("name") or ""
        # Google Benchmark appends "/iterations:N" to the registered name
        # when ->Iterations(N) is used. Strip it so the test_name matches
        # the name we registered via ->Name("benchmarkN").
        if "/iterations:" in test_name:
            test_name = test_name.split("/iterations:", 1)[0]
        unit = entry.get("time_unit", "ns")

        metrics = [
            {
                "name": "real_time",
                "unit": unit,
                "value": entry["real_time"],
                "direction": "lower_is_better",
            },
            {
                "name": "cpu_time",
                "unit": unit,
                "value": entry["cpu_time"],
                "direction": "lower_is_better",
            },
        ]

        passed = not bool(entry.get("error_occurred", False))

        out.append({
            "timestamp": 0,
            "attributes": {"test_name": test_name},
            "metrics": metrics,
            "passed": passed,
        })

    return out
