"""Parser for memtier_benchmark's default human-readable stdout table.

memtier_benchmark (RedisLabs' Redis/memcached load generator) is *not* a
"run four arbitrary workloads" tool. A single invocation hammers the
server with a configured SET/GET mix and prints an ``ALL STATS`` table —
one row per operation type (``Sets``, ``Gets``, ``Waits``, ``Totals``)::

    ALL STATS
    ===========================================================...
    Type         Ops/sec     Hits/sec   Misses/sec    Avg. Latency ... KB/sec
    -----------------------------------------------------------...
    Sets        27127.17          ---          ---         0.46076 ... 2937.46
    Gets        27125.17        19.99     27105.18         0.45919 ... 1057.93
    Waits           0.00          ---          ---             --- ...    ---
    Totals      54252.34        19.99     27105.18         0.45997 ... 3995.39

The benchzoo memtier framework therefore **deviates** from the canonical
four-benchmark shape (no 2.15 s sleeps): each operation-type row becomes a
``test_name`` (lowercased), mirroring the JSON parser (:mod:`memtier_json`).
The README (``frameworks/database/memtier/README.md``) documents the
deviation; ground-truth checks key off memtier's own numbers (tens of
thousands of ops/s on localhost Redis, sub-millisecond latency).

Two things make the text format awkward, both handled here:

1. **Column widths vary by memtier version**, so we key columns by their
   header name (not byte offset): read the ``Type ... Ops/sec ...``
   header row, map each header label to a metric, then split each data
   row on whitespace and zip values to headers. ``---`` placeholders
   (e.g. ``Hits/sec`` for ``Sets``) are skipped.
2. **It's usually buried in a much larger CI log** — the progress
   ``[RUN #1 …]`` lines, the per-SET/GET latency-distribution histogram,
   and (when read from a GitHub Actions job *log* rather than an
   artifact) a per-line ISO-8601 timestamp prefix and ANSI colour codes.
   We scan for the ``ALL STATS`` header, then read the table beneath it.

See ``frameworks/database/memtier/README.md``.
"""

from __future__ import annotations

import re


# Strip ANSI escapes (CI logs are often colourised).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Optional GitHub-Actions per-line ISO-8601 timestamp prefix. When the
# output is read from a job *log* (no artifact), every line carries one;
# artifact files (output.txt) are clean. Tolerate either.
_TS_RE = re.compile(
    r"^\s*(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?"
)

# Header labels -> (metric_name, unit, direction|None). Keyed by the exact
# column header text memtier prints. Unknown headers are ignored.
_COLUMNS: dict[str, tuple[str, str, str | None]] = {
    "Ops/sec":       ("ops_per_sec",   "ops/s", "higher_is_better"),
    "Hits/sec":      ("hits_per_sec",  "ops/s", None),
    "Misses/sec":    ("misses_per_sec", "ops/s", "lower_is_better"),
    "Avg. Latency":  ("latency_mean",  "ms",    "lower_is_better"),
    "p50 Latency":   ("latency_p50",   "ms",    "lower_is_better"),
    "p90 Latency":   ("latency_p90",   "ms",    "lower_is_better"),
    "p95 Latency":   ("latency_p95",   "ms",    "lower_is_better"),
    "p99 Latency":   ("latency_p99",   "ms",    "lower_is_better"),
    "p99.9 Latency": ("latency_p999",  "ms",    "lower_is_better"),
    "KB/sec":        ("kb_per_sec",    "kB/s",  "higher_is_better"),
}

# Header tokens. memtier prints "Avg. Latency", "p50 Latency", etc. as
# two whitespace-separated words, so we cannot naively split the header on
# whitespace. Instead match the known column labels in header order.
_HEADER_TOKEN_RE = re.compile(
    r"Type|Ops/sec|Hits/sec|Misses/sec|Avg\. Latency|"
    r"p\d+(?:\.\d+)? Latency|KB/sec"
)

# The header row must contain at least the Type + Ops/sec + a latency
# column to be the ALL STATS header (and not, say, the latency-histogram
# "Type  <= msec  Percent" header).
_IS_STATS_HEADER = re.compile(r"\bType\b").search


def _clean(raw: str) -> str:
    return _TS_RE.sub("", _ANSI_RE.sub("", raw)).rstrip("\n")


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    lines = [_clean(ln) for ln in content.splitlines()]

    # Find the ALL STATS header row: the line that starts with "Type" and
    # carries "Ops/sec". (The latency-distribution table header is
    # "Type  <= msec  Percent" — no "Ops/sec" — so it won't match.)
    header_idx = None
    headers: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("Type") or "Ops/sec" not in stripped:
            continue
        headers = _HEADER_TOKEN_RE.findall(stripped)
        if "Type" in headers and "Ops/sec" in headers:
            header_idx = i
            break
    if header_idx is None:
        return []

    # Column order after the leading "Type" label.
    value_headers = [h for h in headers if h != "Type"]

    out: list[dict] = []
    for line in lines[header_idx + 1:]:
        stripped = line.strip()
        if not stripped:
            # Blank line ends the table block.
            break
        # Skip rule lines made of dashes/equals.
        if set(stripped) <= set("-= "):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            continue
        op = parts[0]
        # A data row begins with an operation type word followed by numbers
        # (or ---). If the first token isn't an alpha word, this isn't a row.
        if not op[0].isalpha():
            break
        values = parts[1:]
        # memtier always prints exactly one value (number or "---") per
        # column; if the count doesn't line up, the table has ended (e.g.
        # we ran into the next section).
        if len(values) != len(value_headers):
            break

        metrics: list[dict] = []
        for header, token in zip(value_headers, values):
            if token == "---":
                continue
            spec = _COLUMNS.get(header)
            if spec is None:
                continue
            try:
                value = float(token)
            except ValueError:
                continue
            name, unit, direction = spec
            metric: dict = {"name": name, "unit": unit, "value": value}
            if direction is not None:
                metric["direction"] = direction
            metrics.append(metric)

        out.append({
            "test": {"test_name": op.lower()},
            "run": {"passed": True},
            "env": {"framework": {"name": "memtier"}},
            "metrics": metrics,
        })

    return out
