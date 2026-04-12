"""Parser for Lighthouse JSON audit output.

Lighthouse audits a single page load and emits a large JSON document
with a top-level ``audits`` dict. Each audit has an ``id``, ``title``,
``score``, ``scoreDisplayMode``, and — for numeric audits — a
``numericValue`` and ``numericUnit``.

Unlike the other frameworks in the corpus, Lighthouse does NOT run the
canonical four-test sample benchmark. It runs ONE audit (a single page
load) and reports web-vitals metrics (LCP, FCP, CLS, TBT, Speed Index,
TTI, …). We therefore emit a **single Nyrkiö dict** with
``attributes["test_name"] = "homepage"`` and one metric per web vital.

Web vitals we emit:

- ``first-contentful-paint`` → ``fcp``
- ``largest-contentful-paint`` → ``lcp``
- ``cumulative-layout-shift`` → ``cls`` (unitless)
- ``total-blocking-time`` → ``tbt``
- ``speed-index`` → ``speed_index``
- ``interactive`` → ``tti``
- ``server-response-time`` → ``server_response_time``
- ``total-byte-weight`` → ``total_byte_weight`` (unit ``byte``)

All timings are ``lower_is_better`` with unit ``"ms"`` (Lighthouse's
``numericUnit`` is the verbose ``"millisecond"``, which we normalize).
``total-byte-weight``'s unit is ``byte``. ``cumulative-layout-shift``
is unitless (we use the empty string).

``fetchTime`` is **never** used for the Nyrkiö ``timestamp`` — see
``docs/design.md`` field semantics. We keep it in ``extra_info`` for
reference.

See ``frameworks/frontend/lighthouse/README.md``.
"""

from __future__ import annotations

import json


_UNIT_NORMALIZE = {
    "millisecond": "ms",
    "byte": "byte",
    "unitless": "",
}

# Map Lighthouse audit id → Nyrkiö metric name.
_AUDITS = {
    "first-contentful-paint": "fcp",
    "largest-contentful-paint": "lcp",
    "cumulative-layout-shift": "cls",
    "total-blocking-time": "tbt",
    "speed-index": "speed_index",
    "interactive": "tti",
    "server-response-time": "server_response_time",
    "total-byte-weight": "total_byte_weight",
}


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    doc = json.loads(content)

    audits = doc.get("audits", {})
    metrics: list[dict] = []

    for audit_id, metric_name in _AUDITS.items():
        audit = audits.get(audit_id)
        if not audit:
            continue
        numeric_value = audit.get("numericValue")
        if numeric_value is None:
            # Audit ran but produced no numeric result (notApplicable,
            # or the audit only has a score). Skip it — we don't emit
            # boolean audits as metrics.
            continue
        unit_raw = audit.get("numericUnit", "")
        unit = _UNIT_NORMALIZE.get(unit_raw, unit_raw)
        metrics.append({
            "name": metric_name,
            "unit": unit,
            "value": numeric_value,
            "direction": "lower_is_better",
        })

    extra_info: dict = {}
    if "fetchTime" in doc:
        extra_info["fetch_time"] = doc["fetchTime"]
    if "lighthouseVersion" in doc:
        extra_info["lighthouse_version"] = doc["lighthouseVersion"]
    if "userAgent" in doc:
        extra_info["user_agent"] = doc["userAgent"]

    result: dict = {
        "timestamp": 0,
        "attributes": {"test_name": "homepage"},
        "metrics": metrics,
        "passed": True,
    }
    if extra_info:
        result["extra_info"] = extra_info
    return [result]
