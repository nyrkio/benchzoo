"""Parser for Apache JMeter's non-GUI **stdout** Summariser line.

When JMeter runs in non-GUI mode (``-n``), its built-in *Summariser*
prints a one-line cumulative summary to **stdout** (and the run log) at
the end of the test — and periodically for long tests. This is what
lands in the CI job log even when the per-sample CSV (see
:mod:`jmeter_csv`) is only uploaded as an artifact. The line looks
like::

    summary =   1000 in 00:00:01 = 1034.1/s Avg:     0 Min:     0 Max:    36 Err:     0 (0.00%)

Fields (all timings in **milliseconds**):

- ``1000``       — total samples (requests) so far
- ``00:00:01``   — elapsed wall time HH:MM:SS
- ``1034.1/s``   — throughput, requests per second
- ``Avg``        — mean sample/response time, ms
- ``Min``/``Max``— min/max sample time, ms
- ``Err``        — error count and percentage

JMeter emits running ``summary +`` lines during a long test and a
final cumulative ``summary =`` line; some builds also print a
``summary =`` with a non-default label name in place of ``summary``.
We read the **last cumulative** (``=``) line, which is the run total —
matching ``frameworks/loadtest/jmeter/`` which runs a single
``homepage`` test plan (10 threads x 100 loops = 1000 requests).

Two quirks handled here:

1. **GitHub Actions log prefix** — every captured line is prefixed
   with an ISO-8601 timestamp (``2026-04-13T00:00:55.9937699Z ``); we
   strip ANSI codes and scan anywhere in the line, so the prefix is
   harmless.
2. **The test name is not benchmark1..4.** JMeter measures HTTP
   request latency under load, not an arbitrary sleep/loop/write, so
   the canonical four benchmarks do not apply (see the framework
   README). The single test is reported as ``homepage`` (the sampler
   label), matching the CSV parser.

See ``frameworks/loadtest/jmeter/README.md``.
"""

from __future__ import annotations

import re


# Strip ANSI escape codes (JMeter/log4j colorize some lines).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# The Summariser cumulative line. ``summary`` is the default label; we
# anchor on the literal so we never collide with another framework's
# log. ``=`` is the cumulative total (``+`` lines are interim deltas).
_SUMMARY_RE = re.compile(
    r"summary\s*=\s*"
    r"(?P<count>\d+)\s+in\s+"
    r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})\s*=\s*"
    r"(?P<tput>[0-9.]+)/s\s+"
    r"Avg:\s*(?P<avg>\d+)\s+"
    r"Min:\s*(?P<min>\d+)\s+"
    r"Max:\s*(?P<max>\d+)\s+"
    r"Err:\s*(?P<err>\d+)\s*\(\s*(?P<errpct>[0-9.]+)%\)"
)


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    last = None
    for raw in content.splitlines():
        line = _ANSI_RE.sub("", raw)
        m = _SUMMARY_RE.search(line)
        if m:
            last = m  # keep the final cumulative line

    if last is None:
        return []

    count = int(last.group("count"))
    duration_s = (
        int(last.group("h")) * 3600
        + int(last.group("m")) * 60
        + int(last.group("s"))
    )
    throughput = float(last.group("tput"))
    avg = float(last.group("avg"))
    mn = float(last.group("min"))
    mx = float(last.group("max"))
    err = int(last.group("err"))
    errpct = float(last.group("errpct"))

    metrics = [
        {"name": "elapsed_mean", "unit": "ms", "value": avg,
         "direction": "lower_is_better"},
        {"name": "elapsed_min", "unit": "ms", "value": mn,
         "direction": "lower_is_better"},
        {"name": "elapsed_max", "unit": "ms", "value": mx,
         "direction": "lower_is_better"},
        {"name": "throughput", "unit": "req/s", "value": throughput,
         "direction": "higher_is_better"},
        {"name": "total_requests", "unit": "count", "value": float(count),
         "direction": "higher_is_better"},
        {"name": "error_count", "unit": "count", "value": float(err),
         "direction": "lower_is_better"},
        {"name": "error_rate", "unit": "percent", "value": errpct,
         "direction": "lower_is_better"},
        {"name": "duration", "unit": "s", "value": float(duration_s),
         "direction": "lower_is_better"},
    ]

    return [{
        "test": {"test_name": "homepage"},
        "run": {"passed": err == 0},
        "env": {"framework": {"name": "jmeter"}},
        "metrics": metrics,
    }]
