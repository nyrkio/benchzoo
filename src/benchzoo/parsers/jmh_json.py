"""Parser for JMH's ``-rf json`` output.

JMH's JSON format is a top-level **array**, one entry per ``@Benchmark``
method that ran. Each entry has a fully-qualified ``benchmark`` name
(e.g. ``io.nyrkio.benchzoo.jmh.SampleBenchmark.benchmark1``), a ``mode``
(``"avgt"``, ``"thrpt"``, ``"sample"``, ``"ss"``), and a
``primaryMetric`` dict carrying ``score``, ``scoreError``, and
``scoreUnit`` (typically ``"ms/op"`` for ``avgt``).

See ``frameworks/language/jmh/README.md`` for the parser notes this
implementation follows.
"""

from __future__ import annotations

import json


# JMH modes where a lower score is better (time-per-op) vs. higher
# (ops-per-time).
_LOWER_IS_BETTER_MODES = {"avgt", "sample", "ss"}
_HIGHER_IS_BETTER_MODES = {"thrpt"}


def _direction_for_mode(mode: str) -> str | None:
    if mode in _LOWER_IS_BETTER_MODES:
        return "lower_is_better"
    if mode in _HIGHER_IS_BETTER_MODES:
        return "higher_is_better"
    return None


def _short_name(fqn: str) -> str:
    """Strip the Java package/class prefix from a JMH benchmark name.

    ``io.nyrkio.benchzoo.jmh.SampleBenchmark.benchmark1`` -> ``benchmark1``.
    """
    return fqn.rsplit(".", 1)[-1]


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    out: list[dict] = []
    for entry in doc:
        mode = entry.get("mode", "")
        direction = _direction_for_mode(mode)

        primary = entry.get("primaryMetric", {})
        unit = primary.get("scoreUnit", "")

        score_metric: dict = {
            "name": "score",
            "unit": unit,
            "value": primary["score"],
        }
        if direction is not None:
            score_metric["direction"] = direction

        error_metric: dict = {
            "name": "score_error",
            "unit": unit,
            "value": primary.get("scoreError"),
        }
        if direction is not None:
            error_metric["direction"] = direction

        params: dict = {}
        for key in ("mode", "threads", "forks",
                    "warmupIterations", "measurementIterations"):
            if key in entry:
                params[key] = entry[key]
        if entry.get("params"):
            params.update(entry["params"])

        test: dict = {"test_name": _short_name(entry["benchmark"])}
        fqn = entry.get("benchmark", "")
        if "." in fqn:
            test["group"] = fqn.rsplit(".", 1)[0]
        if params:
            test["params"] = params

        env: dict = {"framework": {"name": "jmh"}}
        if entry.get("jmhVersion"):
            env["framework"]["version"] = entry["jmhVersion"]
        vm_name = entry.get("vmName")
        vm_ver = entry.get("vmVersion")
        if vm_name and vm_ver:
            env["runtime"] = f"{vm_name} {vm_ver}"
        elif entry.get("jdkVersion"):
            env["runtime"] = f"JDK {entry['jdkVersion']}"

        result: dict = {
            "test": test,
            "run": {"passed": True},
            "env": env,
            "metrics": [score_metric, error_metric],
        }

        out.append(result)

    return out
