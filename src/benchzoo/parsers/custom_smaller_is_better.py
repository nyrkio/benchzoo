"""Parser for the ``customSmallerIsBetter`` JSON escape-hatch format.

The input is a flat JSON array of ``{name, unit, value, extra?}`` objects.
Every value in this variant is a duration or latency, so every metric's
``direction`` is ``"lower_is_better"``.

See ``frameworks/generic/custom-json/README.md`` for the format spec.
"""

from __future__ import annotations

from ._custom_json_common import parse_custom_json


def parse(content: bytes | str) -> list[dict]:
    return parse_custom_json(content, direction="lower_is_better")
