"""Parser for redis-benchmark's default (non-CSV) human-readable output.

A single redis-benchmark invocation iterates over several built-in
command types (SET, GET, INCR, LPUSH, RPUSH, MSET, …) and prints, per
command, a block delimited by a ``====== <CMD> ======`` banner. Each
block ends with a ``Summary:`` section carrying the same numbers the
``--csv`` output emits::

    ====== SET ======
      100000 requests completed in 3.54 seconds
      50 parallel clients
      ...

    Summary:
      throughput summary: 28232.64 requests per second
      latency summary (msec):
              avg       min       p50       p95       p99       max
            1.504     0.080     1.391     2.711     3.711    14.127

We key on the ``====== <CMD> ======`` banner for the test name and read
the ``Summary:`` block for the metrics, preferring it over re-deriving
values from the verbose percentile tables (per the README). The command
name can contain spaces (e.g. ``MSET (10 keys)``).

**Deviation from the canonical sample benchmark.** redis-benchmark does
not run the canonical four sleeps/writes — there is no idiomatic way to
express them. Each command type becomes a ``test_name`` instead, and the
ground truth is redis-benchmark's own characteristic numbers (tens of
thousands of ops/s, sub-2 ms average latency on localhost). See
``frameworks/database/redis-benchmark/README.md``.

The metrics decompose as:

- throughput — unit ``"ops/s"``, ``higher_is_better``
- avg/min/p50/p95/p99/max latency — unit ``"ms"``, ``lower_is_better``

Although redis-benchmark redirects this output to a file (so the GitHub
Actions *artifact* is the source of truth, not the job log), the parser
still tolerates a per-line ISO-8601 timestamp prefix and ANSI colour
codes so it works whether fed an artifact or a log slice.

See ``frameworks/database/redis-benchmark/README.md``.
"""

from __future__ import annotations

import re


# Strip ANSI escapes and an optional GitHub-Actions ISO-8601 timestamp
# prefix from each line, so the parser works on artifacts and log slices.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_TS_RE = re.compile(r"^\s*\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+")

# Block boundary + test name: "====== MSET (10 keys) ======". The name
# may carry spaces/parens, so capture lazily up to the trailing banner.
_BANNER_RE = re.compile(r"^=+\s*(.+?)\s*=+\s*$")

# "throughput summary: 28232.64 requests per second"
_THROUGHPUT_RE = re.compile(
    r"throughput summary:\s*([0-9.]+)\s*requests per second"
)

# The latency table header and its single data row of six floats:
#         avg       min       p50       p95       p99       max
#       1.504     0.080     1.391     2.711     3.711    14.127
_LATENCY_HEADER_RE = re.compile(
    r"^\s*avg\s+min\s+p50\s+p95\s+p99\s+max\s*$"
)
_FLOATS_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?")

_LATENCY_NAMES = ["avg", "min", "p50", "p95", "p99", "max"]


def _clean(line: str) -> str:
    return _TS_RE.sub("", _ANSI_RE.sub("", line))


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    lines = [_clean(ln) for ln in content.splitlines()]

    # Find every banner and slice the content into per-command blocks.
    banners: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = _BANNER_RE.match(line)
        if m:
            banners.append((i, m.group(1).strip()))

    out: list[dict] = []
    for idx, (start, name) in enumerate(banners):
        end = banners[idx + 1][0] if idx + 1 < len(banners) else len(lines)
        block = lines[start:end]

        metrics: list[dict] = []

        for j, line in enumerate(block):
            tm = _THROUGHPUT_RE.search(line)
            if tm:
                metrics.append({
                    "name": "throughput",
                    "unit": "ops/s",
                    "value": float(tm.group(1)),
                    "direction": "higher_is_better",
                })
            if _LATENCY_HEADER_RE.match(line):
                # The data row is the next non-blank line after the header.
                for k in range(j + 1, len(block)):
                    nxt = block[k].strip()
                    if not nxt:
                        continue
                    vals = _FLOATS_RE.findall(nxt)
                    if len(vals) >= len(_LATENCY_NAMES):
                        for metric_name, val in zip(_LATENCY_NAMES, vals):
                            metrics.append({
                                "name": f"{metric_name}_latency",
                                "unit": "ms",
                                "value": float(val),
                                "direction": "lower_is_better",
                            })
                    break

        # "record but do not filter": a block missing its numbers is
        # still emitted, marked not-passed.
        passed = any(m["name"] == "throughput" for m in metrics)
        out.append({
            "test": {"test_name": name},
            "run": {"passed": passed},
            "env": {"framework": {"name": "redis-benchmark"}},
            "metrics": metrics,
        })

    return out
