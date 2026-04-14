"""Parser for pytest-benchmark's ``--benchmark-json`` output.

Emits the **v2 schema** (see ``docs/schema-v2.md``). pytest-benchmark
is unusually rich: it carries ``commit_info``, ``machine_info``, and
per-benchmark ``stats``, so it exercises every sub-document.
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

    commit_info = doc.get("commit_info") or {}
    machine_info = doc.get("machine_info") or {}
    cpu_info = machine_info.get("cpu") or {}

    commit = {}
    if commit_info.get("project"):
        commit["repo"] = commit_info["project"]
    if commit_info.get("id"):
        commit["sha"] = commit_info["id"]
    if commit_info.get("branch"):
        commit["ref"] = commit_info["branch"]
    t = _parse_iso(commit_info.get("time"))
    if t is not None:
        commit["commit_time"] = t

    run: dict = {"passed": True}
    t = _parse_iso(doc.get("datetime"))
    if t is not None:
        run["test_time"] = t

    env = {}
    if machine_info.get("system"):
        env["os"] = machine_info["system"]
    if machine_info.get("machine"):
        env["arch"] = machine_info["machine"]
    if cpu_info.get("brand_raw"):
        env["cpu"] = cpu_info["brand_raw"]
    if cpu_info.get("count"):
        env["cpu_count"] = cpu_info["count"]
    impl = machine_info.get("python_implementation")
    pyver = machine_info.get("python_version")
    if impl and pyver:
        env["runtime"] = f"{impl} {pyver}"
    framework = {"name": "pytest-benchmark"}
    if doc.get("version"):
        framework["version"] = doc["version"]
    env["framework"] = framework

    out: list[dict] = []
    for entry in doc.get("benchmarks", []):
        stats = entry["stats"]

        raw_name = entry["name"]
        test_name = raw_name[len("test_"):] if raw_name.startswith("test_") else raw_name

        test = {"test_name": test_name}
        if entry.get("group") is not None:
            test["group"] = entry["group"]
        if entry.get("param"):
            test["params"] = {"param": entry["param"]}

        metrics = [
            {"name": "mean",   "unit": "s",     "value": stats["mean"],   "direction": "lower_is_better"},
            {"name": "min",    "unit": "s",     "value": stats["min"],    "direction": "lower_is_better"},
            {"name": "max",    "unit": "s",     "value": stats["max"],    "direction": "lower_is_better"},
            {"name": "stddev", "unit": "s",     "value": stats["stddev"], "direction": "lower_is_better"},
            {"name": "median", "unit": "s",     "value": stats["median"], "direction": "lower_is_better"},
            {"name": "ops",    "unit": "ops/s", "value": stats["ops"],    "direction": "higher_is_better"},
        ]

        result = {
            "test": test,
            "run": dict(run),
            "metrics": metrics,
        }
        if commit:
            result["commit"] = commit
        if env:
            result["env"] = env

        out.append(result)

    return out
