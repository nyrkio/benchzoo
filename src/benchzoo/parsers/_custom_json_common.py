"""Shared implementation for the customBiggerIsBetter / customSmallerIsBetter
JSON escape-hatch parsers.

The two public parser modules differ only in the ``direction`` they assign
to every emitted metric; the on-disk shape is identical.
"""

from __future__ import annotations

import json


def parse_custom_json(content: bytes | str, *, direction: str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    out: list[dict] = []
    for entry in doc:
        name = entry["name"]
        metric = {
            "name": name,
            "unit": entry["unit"],
            "value": entry["value"],
            "direction": direction,
        }
        d: dict = {
            "test": {"test_name": name},
            "run": {"passed": True},
            "env": {"framework": {"name": "custom-json"}},
            "metrics": [metric],
        }
        if "extra" in entry:
            d["extra_info"] = {"extra": entry["extra"]}
        out.append(d)

    return out
