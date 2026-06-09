"""Parser for BenchmarkDotNet's human-readable console summary table.

This is the third capture format for BenchmarkDotNet (alongside the JSON
and CSV exporters). It's the output every user sees when running
``dotnet run`` interactively, and what benchzoo's CI tees to
``output.txt``. The interesting block is the ``// * Summary *``
markdown table::

    | Method     | Mean           | Error      | StdDev   | Median           |
    |----------- |---------------:|-----------:|---------:|-----------------:|
    | Benchmark1 | 2,150,299.4 us | 5,382.3 us | 295.0 us | 2,150,175.087 us |
    | Benchmark2 |       101.9 us | 3,104.5 us | 170.2 us |         3.716 us |
    | Benchmark3 |     5,289.7 us | 7,715.3 us | 422.9 us |     5,104.289 us |
    | Benchmark4 | 1,150,289.7 us | 5,460.3 us | 299.3 us | 1,150,121.799 us |

Format quirks handled here:

1. **The unit auto-scales per cell** (``ns`` / ``us`` / ``µs`` / ``ms`` /
   ``s``) depending on each value's magnitude — and BenchmarkDotNet picks
   a unit per *column* but renders it in every cell, so a raw number is
   meaningless without its suffix. We normalise every value to
   **nanoseconds** for consistency with :mod:`benchmarkdotnet_json` and
   :mod:`benchmarkdotnet_csv`.
2. **Thousands separators** — values like ``2,150,299.4`` carry commas
   that must be stripped before ``float()``.
3. **Column set varies** — the table always has ``Method`` and ``Mean``
   but the rest (``Error``, ``StdDev``, ``Median``, sometimes ``Min`` /
   ``Max``) depend on configuration. We read the header row to discover
   which columns exist and map each known numeric column to a metric.
4. **It's buried in a large CI log** — environment banner, per-benchmark
   detailed-results blocks (which *also* contain ``Mean = ...`` lines,
   deliberately ignored), histograms, warnings, legends. We locate the
   markdown table by its ``| Method ... |`` header and the ``---`` rule
   directly beneath it, then read rows until the table ends.
5. **GitHub Actions log timestamp prefix** — when captured from a job
   log every line is prefixed with an ISO-8601 timestamp
   (``2026-06-07T22:11:54.8735220Z ``). We strip it. ANSI colour codes
   are stripped too.

``test_name`` is normalised from ``Method`` (``"Benchmark1"`` →
``"benchmark1"``) to match the lowercase convention used across the
benchzoo corpus.

See ``frameworks/language/benchmarkdotnet/README.md``.
"""

from __future__ import annotations

import re


# GitHub Actions log line timestamp prefix, e.g.
# "2026-06-07T22:11:54.8735220Z ".
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T[\d:.]+Z\s")

# Strip ANSI escape codes just in case the console output was colorized.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# A numeric table cell with a unit suffix: "2,150,299.4 us", "3.716 us",
# "101.9 us". µ may be MICRO SIGN (U+00B5) or GREEK MU (U+03BC).
_CELL_RE = re.compile(
    r"^\s*([0-9,]+(?:\.[0-9]+)?)\s*(ns|us|µs|μs|ms|s)\s*$"
)

_TO_NS = {
    "ns": 1.0,
    "us": 1_000.0,
    "µs": 1_000.0,
    "μs": 1_000.0,
    "ms": 1_000_000.0,
    "s": 1_000_000_000.0,
}

# Header columns we turn into metrics, mapped to the emitted metric name.
_METRIC_COLUMNS = {
    "Mean": "mean",
    "Median": "median",
    "StdDev": "stddev",
    "Error": "error",
    "Min": "min",
    "Max": "max",
}


def _strip(line: str) -> str:
    line = _ANSI_RE.sub("", line)
    return _TS_RE.sub("", line)


def _cells(row: str) -> list[str]:
    """Split a markdown table row ``| a | b | c |`` into trimmed cells."""
    parts = row.split("|")
    # Drop the empty leading/trailing fragments produced by the outer pipes.
    if parts and parts[0].strip() == "":
        parts = parts[1:]
    if parts and parts[-1].strip() == "":
        parts = parts[:-1]
    return [p.strip() for p in parts]


def _parse_ns(cell: str) -> float | None:
    m = _CELL_RE.match(cell)
    if not m:
        return None
    return float(m.group(1).replace(",", "")) * _TO_NS[m.group(2)]


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    lines = [_strip(ln) for ln in content.splitlines()]

    # Find the summary markdown table: a "| Method | ... |" header row
    # immediately followed by a "|---|---|" separator rule.
    header_idx = None
    headers: list[str] = []
    for i, line in enumerate(lines):
        s = line.strip()
        if not (s.startswith("|") and "Method" in s):
            continue
        cells = _cells(s)
        if not cells or cells[0] != "Method":
            continue
        # Next non-empty line must be the markdown separator rule.
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if set(nxt) <= set("|-: "):
            header_idx = i
            headers = cells
            break

    if header_idx is None:
        return []

    out: list[dict] = []
    for line in lines[header_idx + 2:]:
        s = line.strip()
        if not s.startswith("|"):
            break  # table ended
        if set(s) <= set("|-: "):
            continue  # a stray separator rule
        cells = _cells(s)
        if len(cells) != len(headers):
            continue
        row = dict(zip(headers, cells))
        method = row.get("Method", "")
        if not method:
            continue
        test_name = method[:1].lower() + method[1:]

        metrics = []
        for col, metric_name in _METRIC_COLUMNS.items():
            if col not in row:
                continue
            value = _parse_ns(row[col])
            if value is None:
                continue
            metrics.append({
                "name": metric_name,
                "unit": "ns",
                "value": value,
                "direction": "lower_is_better",
            })
        if not metrics:
            continue
        out.append({
            "test": {"test_name": test_name},
            "run": {"passed": True},
            "env": {"framework": {"name": "benchmarkdotnet"}},
            "metrics": metrics,
        })

    return out
