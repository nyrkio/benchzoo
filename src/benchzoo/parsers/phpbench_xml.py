"""Parser for PHPBench's ``--dump-file`` XML output.

PHPBench emits a rich suite XML with ``<phpbench>`` → ``<suite>`` →
``<benchmark>`` → ``<subject>`` → ``<variant>`` → ``<iteration>``
nesting. Each ``<variant>`` has an ``output-time-unit`` attribute
(``microseconds``, ``milliseconds``, etc.) and carries a ``<stats>``
child with pre-aggregated ``mean``, ``min``, ``max``, ``mode``,
``stdev``, ``rstdev``, ``variance``, ``sum``.

Subject names are like ``benchBenchmark1`` (PHPBench convention).
Parser strips the ``bench`` prefix and lowercases the first
character: ``benchBenchmark1`` → ``benchmark1``.

All stats values are converted to **seconds** based on the variant's
``output-time-unit`` — making the parser's output consistent with
other benchzoo parsers regardless of what precision the user picked.

See ``frameworks/language/phpbench/README.md``.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET


_TIME_UNIT_TO_S = {
    "nanoseconds":  1e-9,
    "microseconds": 1e-6,
    "milliseconds": 1e-3,
    "seconds":      1.0,
}


def _normalize_subject_name(raw: str) -> str:
    """``benchBenchmark1`` → ``benchmark1``."""
    if raw.startswith("bench"):
        tail = raw[len("bench"):]
        return tail[:1].lower() + tail[1:] if tail else tail
    return raw


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    root = ET.fromstring(content)

    out: list[dict] = []
    for subject in root.iter("subject"):
        raw_name = subject.get("name", "").strip()
        if not raw_name:
            continue
        test_name = _normalize_subject_name(raw_name)

        variant = subject.find("variant")
        if variant is None:
            continue

        unit = variant.get("output-time-unit", "microseconds")
        scale = _TIME_UNIT_TO_S.get(unit, 1e-6)

        stats = variant.find("stats")
        metrics: list[dict] = []
        if stats is not None:
            for attr, metric_name in [
                ("mean",  "mean"),
                ("min",   "min"),
                ("max",   "max"),
                ("mode",  "mode"),
                ("stdev", "stddev"),
            ]:
                raw = stats.get(attr)
                if raw is None:
                    continue
                try:
                    metrics.append({
                        "name": metric_name,
                        "unit": "s",
                        "value": float(raw) * scale,
                        "direction": "lower_is_better",
                    })
                except ValueError:
                    continue

            rstdev = stats.get("rstdev")
            if rstdev is not None:
                try:
                    metrics.append({
                        "name": "rstdev",
                        "unit": "",
                        "value": float(rstdev),
                        "direction": "lower_is_better",
                    })
                except ValueError:
                    pass

        extra_info: dict = {
            "revs": int(variant.get("revs") or 0),
            "warmup": int(variant.get("warmup") or 0),
            "output_time_unit": unit,
        }
        # Count iterations.
        iter_count = sum(1 for _ in variant.iter("iteration"))
        if iter_count:
            extra_info["iterations"] = iter_count
        # Look for <group name="..."/> entries inside the subject.
        groups = [g.get("name") for g in subject.iter("group") if g.get("name")]
        if groups:
            extra_info["groups"] = groups

        out.append({
            "timestamp": 0,
            "attributes": {"test_name": test_name},
            "metrics": metrics,
            "extra_info": extra_info,
            "passed": True,
        })

    return out
