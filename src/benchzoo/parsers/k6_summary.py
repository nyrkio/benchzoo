"""Parser for k6's ``--summary-export=summary.json`` output.

The summary file is a single JSON object with a top-level ``metrics``
dict. Each key is a metric name; the value is a dict of aggregate stats
shaped by metric type:

- **Trend** (our custom timings — ``benchmark1`` .. ``benchmark4``):
  ``{avg, min, med, max, "p(90)", "p(95)"}``.
- **Counter** (``data_sent``, ``data_received``, ``iterations``):
  ``{count, rate}``.
- **Gauge** (``vus``, ``vus_max``):
  ``{value, min, max}``.

We only emit Nyrkiö dicts for the custom ``benchmark\\d+`` Trend metrics
— k6's built-ins are out of scope for the sample-benchmark corpus.

See ``frameworks/loadtest/k6/README.md`` for the parser notes this
implementation follows.
"""

from __future__ import annotations

import json
import re


_BENCHMARK_NAME_RE = re.compile(r"^benchmark\d+$")


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    out: list[dict] = []
    metrics_dict = doc.get("metrics", {})
    # Sort by test_name so the returned list order is stable and
    # test_name doesn't depend on JSON key iteration order.
    for name in sorted(metrics_dict):
        if not _BENCHMARK_NAME_RE.match(name):
            continue
        stats = metrics_dict[name]
        metrics = [
            {"name": "avg",    "unit": "ms", "value": stats["avg"],    "direction": "lower_is_better"},
            {"name": "min",    "unit": "ms", "value": stats["min"],    "direction": "lower_is_better"},
            {"name": "median", "unit": "ms", "value": stats["med"],    "direction": "lower_is_better"},
            {"name": "max",    "unit": "ms", "value": stats["max"],    "direction": "lower_is_better"},
            {"name": "p90",    "unit": "ms", "value": stats["p(90)"], "direction": "lower_is_better"},
            {"name": "p95",    "unit": "ms", "value": stats["p(95)"], "direction": "lower_is_better"},
        ]
        out.append({
            "timestamp": 0,
            "attributes": {"test_name": name},
            "metrics": metrics,
            "passed": True,
        })

    return out
