"""Parser for mocha's ``--reporter json`` output.

mocha's JSON reporter emits a single document with::

    {
      "stats":    {"suites": 1, "tests": 4, "passes": 4, ...,
                   "duration": 4311},    # total ms
      "tests":    [ { "title": ..., "fullTitle": ...,
                      "duration": 2153, "err": {} }, ... ],
      "passes":   [ ... same shape, subset ... ],
      "failures": [ ... ],
      "pending":  [ ... ]
    }

We read ``tests[]`` (the full set, including any failures) and emit
one Nyrkiö dict per entry. ``title`` maps to ``test_name`` directly
(no prefix to strip — users choose the label).

Durations are in **milliseconds**. passed = (err is empty dict).

See ``frameworks/unit-or-qa/mocha/README.md``.
"""

from __future__ import annotations

import json


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    out: list[dict] = []
    for entry in doc.get("tests", []):
        title = entry.get("title", "").strip()
        if not title:
            continue

        duration_ms = float(entry.get("duration") or 0)
        err = entry.get("err")
        failed = bool(err) and err != {}

        metrics = [{
            "name": "duration",
            "unit": "ms",
            "value": duration_ms,
            "direction": "lower_is_better",
        }]

        extra_info: dict = {}
        if entry.get("fullTitle") and entry["fullTitle"] != title:
            extra_info["fullTitle"] = entry["fullTitle"]
        if entry.get("speed"):
            extra_info["speed"] = entry["speed"]

        result = {
            "test": {"test_name": title},
            "run": {"passed": not failed},
            "env": {"framework": {"name": "mocha"}},
            "metrics": metrics,
        }
        if extra_info:
            result["extra_info"] = extra_info
        out.append(result)

    return out
