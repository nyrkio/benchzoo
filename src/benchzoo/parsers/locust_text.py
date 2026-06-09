"""Parser for Locust's human-readable console summary table.

When Locust runs ``--headless`` it prints a final summary report to
stdout that benchzoo's ``run.sh`` ``tee``s to ``output.txt`` (and which
GitHub Actions records, with an ISO-8601 timestamp prefix on every line,
in the job log). The report has two tables. The first is the per-request
stats table::

    Type     Name      # reqs      # fails |    Avg     Min     Max    Med |   req/s  failures/s
    --------|---------|-------|-------------|-------|-------|-------|-------|--------|-----------
    GET      /          14619     0(0.00%) |      4       2      67      4 | 1585.66        0.00
    --------|---------|-------|-------------|-------|-------|-------|-------|--------|-----------
             Aggregated 14619     0(0.00%) |      4       2      67      4 | 1585.66        0.00

The second is the percentile table::

    Response time percentiles (approximated)
    Type     Name        50%    66%    75%    80%    90%    95%    98%    99%  99.9% 99.99%   100% # reqs
    --------|-----------|------|------|------|------|------|------|------|------|------|------|------|------
    GET      /            4      5      5      5      5      6      6      7     22     37     68  14619
    --------|-----------|------|------|------|------|------|------|------|------|------|------|------|------
             Aggregated   4      5      5      5      5      6      6      7     22     37     68  14619

This is the textual sibling of :mod:`locust_csv` (which reads the richer
``output_stats.csv``). Both report the same run; this parser exists so a
project that prints the summary to its CI log but does **not** upload the
CSV artifact can still be ingested.

Like ``wrk``/``hey``, Locust is a load-testing tool and does **not**
implement the canonical four sample benchmarks (see
``frameworks/loadtest/locust/README.md``): a single invocation measures
one HTTP endpoint's behavior under sustained concurrent load. We emit one
result per request row (skipping the ``Aggregated`` rollup), with the
``Name`` column as the test name. All latency values are integer
milliseconds; throughput is requests/sec.

The dashed separator rows and the ``Aggregated`` rollup row are skipped.
Every line tolerates an optional GitHub-Actions ISO-8601 timestamp
prefix and ANSI color codes.
"""

from __future__ import annotations

import re


# Strip ANSI escapes (CI logs are often colorized).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Optional GitHub-Actions per-line ISO-8601 timestamp prefix. When the
# summary is read from a job *log* (not the teed artifact), every line is
# prefixed with one of these; the artifact ``output.txt`` is clean.
_TS = r"(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?"

# A row in the FIRST (stats) table:
#   "GET      /      14619     0(0.00%) |   4    2   67    4 | 1585.66   0.00"
# Groups: type, name, reqs, fails, fail_pct, avg, min, max, med, rps, fps.
# The aggregate row has a blank Type, so Type is optional; Name then
# starts the line. We require the "|"-delimited numeric block to anchor
# on a real data row (not a header or dashed separator).
_STATS_RE = re.compile(
    r"^\s*" + _TS +
    r"(?P<type>[A-Z]+)?\s+"
    r"(?P<name>\S+)\s+"
    r"(?P<reqs>\d+)\s+"
    r"(?P<fails>\d+)\((?P<failpct>[0-9.]+)%\)\s*\|\s*"
    r"(?P<avg>\d+)\s+(?P<min>\d+)\s+(?P<max>\d+)\s+(?P<med>\d+)\s*\|\s*"
    r"(?P<rps>[0-9.]+)\s+(?P<fps>[0-9.]+)\s*$"
)

# A row in the SECOND (percentile) table:
#   "GET      /    4   5   5   5   5   6   6   7   22   37   68   14619"
# Groups: type, name, p50..p100 (eleven values), reqs.
_PCT_LABELS = ["p50", "p66", "p75", "p80", "p90", "p95", "p98", "p99",
               "p999", "p9999", "p100"]
_PCT_RE = re.compile(
    r"^\s*" + _TS +
    r"(?P<type>[A-Z]+)?\s+"
    r"(?P<name>\S+)\s+"
    + r"\s+".join(rf"(?P<p{i}>\d+)" for i in range(11)) +
    r"\s+(?P<reqs>\d+)\s*$"
)


def _key(type_: str | None, name: str) -> str:
    type_ = (type_ or "").strip()
    return f"{type_} {name}".strip() if type_ else name


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    # Accumulate metrics per request key across the two tables, then emit
    # one result per key (preserving first-seen order).
    order: list[str] = []
    acc: dict[str, dict] = {}

    def slot(key: str) -> dict:
        if key not in acc:
            order.append(key)
            acc[key] = {"metrics": [], "passed": True}
        return acc[key]

    for raw in content.splitlines():
        line = _ANSI_RE.sub("", raw)

        m = _STATS_RE.match(line)
        if m:
            name = m.group("name")
            # Skip the aggregate rollup row.
            if name == "Aggregated":
                continue
            key = _key(m.group("type"), name)
            s = slot(key)
            fails = int(m.group("fails"))
            if fails:
                s["passed"] = False
            s["metrics"].extend([
                {"name": "latency_avg", "unit": "ms",
                 "value": float(m.group("avg")), "direction": "lower_is_better"},
                {"name": "latency_min", "unit": "ms",
                 "value": float(m.group("min")), "direction": "lower_is_better"},
                {"name": "latency_max", "unit": "ms",
                 "value": float(m.group("max")), "direction": "lower_is_better"},
                {"name": "latency_median", "unit": "ms",
                 "value": float(m.group("med")), "direction": "lower_is_better"},
                {"name": "requests_per_sec", "unit": "ops/s",
                 "value": float(m.group("rps")), "direction": "higher_is_better"},
                {"name": "failures_per_sec", "unit": "ops/s",
                 "value": float(m.group("fps")), "direction": "lower_is_better"},
            ])
            s["request_count"] = int(m.group("reqs"))
            s["failure_count"] = fails
            continue

        m = _PCT_RE.match(line)
        if m:
            name = m.group("name")
            if name == "Aggregated":
                continue
            key = _key(m.group("type"), name)
            s = slot(key)
            for i, label in enumerate(_PCT_LABELS):
                s["metrics"].append({
                    "name": f"latency_{label}", "unit": "ms",
                    "value": float(m.group(f"p{i}")),
                    "direction": "lower_is_better",
                })
            continue

    out: list[dict] = []
    for key in order:
        s = acc[key]
        result = {
            "test": {"test_name": key},
            "run": {"passed": s["passed"]},
            "env": {"framework": {"name": "locust"}},
            "metrics": s["metrics"],
        }
        extra: dict = {}
        if "request_count" in s:
            extra["request_count"] = s["request_count"]
        if "failure_count" in s:
            extra["failure_count"] = s["failure_count"]
        if extra:
            result["extra_info"] = extra
        out.append(result)
    return out
