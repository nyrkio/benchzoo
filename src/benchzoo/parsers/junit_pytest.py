"""Parser for pytest's ``--junitxml`` output, with pytest-benchmark augmentations.

pytest's junit XML is the usual ``<testsuites>/<testsuite>/<testcase>``
shape, with a ``time`` attribute on each ``<testcase>`` giving pytest's
native per-test wall-clock duration (seconds). When pytest-benchmark is
active **and configured to emit its stats into junit**, each benchmarked
``<testcase>`` also carries a ``<properties>`` child with
``<property name="..." value="..."/>`` entries for ``min``, ``max``,
``mean``, ``median``, ``stddev``, ``rounds``, ``iterations``, ``ops``,
``iqr``, ``q1``, ``q3``, etc. Not every pytest-benchmark configuration
writes these — plain junit output from a benchmark run may contain only
the ``time`` attribute, in which case we fall back to emitting a single
``duration`` metric per the "unit-test runner as timing source" use case
from ``docs/design.md``.

``<failure>`` or ``<error>`` children on a testcase cause ``passed:
False``. Pure unit tests without benchmark properties still produce a
result dict carrying their ``time`` attribute — that's deliberate: a
stable test name with a stable wall time is a usable performance time
series, even if it wasn't set up as a benchmark.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET


# Benchmark-stat property names we know how to emit as metrics.
# Everything in this table is a duration in seconds with lower_is_better,
# except ``ops`` which is ops/s with higher_is_better.
_SECONDS_STATS = ("min", "max", "mean", "median", "stddev", "iqr", "q1", "q3")


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    root = ET.fromstring(content)

    out: list[dict] = []
    for testcase in root.iter("testcase"):
        name = testcase.get("name", "")
        # Strip the conventional "test_" prefix so the test name matches
        # what other pytest-benchmark parsers emit.
        test_name = name[len("test_"):] if name.startswith("test_") else name

        passed = (
            testcase.find("failure") is None
            and testcase.find("error") is None
        )

        # Collect benchmark stats from <properties>/<property>, if any.
        props: dict[str, str] = {}
        properties_el = testcase.find("properties")
        if properties_el is not None:
            for prop in properties_el.findall("property"):
                pname = prop.get("name")
                pvalue = prop.get("value")
                if pname is not None and pvalue is not None:
                    props[pname] = pvalue

        metrics: list[dict] = []
        extra_info: dict = {}

        for stat in _SECONDS_STATS:
            if stat in props:
                metrics.append({
                    "name": stat,
                    "unit": "s",
                    "value": float(props[stat]),
                    "direction": "lower_is_better",
                })
        if "ops" in props:
            metrics.append({
                "name": "ops",
                "unit": "ops/s",
                "value": float(props["ops"]),
                "direction": "higher_is_better",
            })
        for counter in ("rounds", "iterations"):
            if counter in props:
                try:
                    extra_info[counter] = int(float(props[counter]))
                except ValueError:
                    extra_info[counter] = props[counter]

        # Fallback: no pytest-benchmark properties — emit pytest's own
        # per-test wall-clock as a single "duration" metric. This is the
        # "unit-test runner as a timing source" use case.
        if not metrics:
            time_attr = testcase.get("time")
            if time_attr is not None:
                metrics.append({
                    "name": "duration",
                    "unit": "s",
                    "value": float(time_attr),
                    "direction": "lower_is_better",
                })

        result: dict = {
            "timestamp": 0,
            "attributes": {"test_name": test_name},
            "metrics": metrics,
            "passed": passed,
        }
        if extra_info:
            result["extra_info"] = extra_info

        out.append(result)

    return out
