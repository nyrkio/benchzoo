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

import datetime as _dt
import json


def _parse_iso(ts: str | None) -> int | None:
    if not ts:
        return None
    try:
        return int(_dt.datetime.fromisoformat(ts).timestamp())
    except ValueError:
        return None


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    ctx = doc.get("context") or {}
    env: dict = {}
    if ctx.get("num_cpus"):
        env["cpu_count"] = ctx["num_cpus"]
    framework = {"name": "google-benchmark"}
    if ctx.get("library_version"):
        framework["version"] = ctx["library_version"]
    env["framework"] = framework

    run_base: dict = {"passed": True}
    t = _parse_iso(ctx.get("date"))
    if t is not None:
        run_base["test_time"] = t

    sut: dict = {}
    if ctx.get("executable"):
        sut["name"] = ctx["executable"]

    extras: dict = {}
    for k in ("host_name", "caches", "mhz_per_cpu", "cpu_scaling_enabled",
              "library_build_type"):
        if ctx.get(k) is not None:
            extras[k] = ctx[k]

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

        run = dict(run_base)
        run["passed"] = passed

        result: dict = {
            "test": {"test_name": test_name},
            "run": run,
            "env": env,
            "metrics": metrics,
        }
        if sut:
            result["sut"] = sut
        if extras:
            result["extra_info"] = dict(extras)
        out.append(result)

    return out
