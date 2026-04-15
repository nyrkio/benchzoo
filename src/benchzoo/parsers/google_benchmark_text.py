"""Parser for Google Benchmark's console/text output.

Google Benchmark emits a banner (host line, CPU caches, load average)
followed by a table of benchmark results:

.. code-block:: text

    2026-04-12T07:13:21+00:00
    Running ./build/sample_benchmark
    Run on (2 X 2872.85 MHz CPU s)
    CPU Caches:
      L1 Data 32 KiB (x1)
      ...
    Load Average: 0.99, 0.42, 0.15
    ------------------------------------------------------------------
    Benchmark                        Time             CPU   Iterations
    ------------------------------------------------------------------
    benchmark1/iterations:1       2150 ms        0.043 ms            1
    benchmark2                   0.000 ms        0.000 ms      1948695

A single log can contain several such blocks back-to-back — a CI step
that runs multiple benchmark executables will emit one banner + table
per executable. This parser handles that.

Each data row is whitespace-delimited:

    NAME    REAL   T_UNIT   CPU   T_UNIT   ITERATIONS   [k=v k=v …]

The optional trailing tokens are Google Benchmark's "UserCounters":
arbitrary ``key=value`` pairs where the value carries an SI or binary
suffix (``18.676M/s``, ``4.16656Mi``). We preserve the suffix as the
metric's ``unit`` rather than trying to normalise to base units —
downstream consumers typically want to display what the framework
reported.

Log lines may be prefixed with a GitHub Actions ISO-8601 timestamp
(``2026-03-25T12:31:30.4598563Z ``); the parser strips that prefix so
either raw or CI-captured output is accepted.
"""

from __future__ import annotations

import re


_GH_ACTIONS_PREFIX = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+"
)

_RUNNING = re.compile(r"^Running\s+(\S+)\s*$")
_SEPARATOR = re.compile(r"^-{3,}\s*$")
_HEADER = re.compile(r"^Benchmark\s+Time\s+CPU\s+Iterations")
_TIME_UNITS = {"s", "ms", "us", "ns"}

# `NAME  REAL T_UNIT  CPU T_UNIT  ITERATIONS [counters…]`
# NAME tolerates template-args `<A, B>` and `/param:N` suffixes but no
# unescaped whitespace; the whitespace split is what separates name
# from columns.
_NUM = r"[0-9]+(?:\.[0-9]*)?(?:[eE][-+]?[0-9]+)?"
_COUNTER_VALUE = re.compile(rf"^({_NUM})(.*)$")

# Counters whose direction we can infer. Everything else is left
# without a direction — the parser is honest about not knowing.
_HIGHER_BETTER_SUFFIXES = ("per_second", "_throughput", "_tps", "_qps")


def _strip_gh_prefix(line: str) -> str:
    m = _GH_ACTIONS_PREFIX.match(line)
    return line[m.end():] if m else line


def _parse_counter(tok: str) -> dict | None:
    """Turn a ``key=value[unit]`` token into a metric dict, or None."""
    if "=" not in tok:
        return None
    name, raw = tok.split("=", 1)
    m = _COUNTER_VALUE.match(raw)
    if not m:
        return None
    try:
        value = float(m.group(1))
    except ValueError:
        return None
    unit = m.group(2).strip()
    metric: dict = {"name": name, "value": value}
    if unit:
        metric["unit"] = unit
    if any(name.endswith(s) for s in _HIGHER_BETTER_SUFFIXES):
        metric["direction"] = "higher_is_better"
    return metric


def _parse_row(line: str) -> dict | None:
    """Turn one data row into a parsed record, or None if malformed."""
    toks = line.split()
    if len(toks) < 6:
        return None
    name = toks[0]
    # The first three "value / unit / value / unit / iterations" tokens
    # must conform to the column shape; anything else is not a data row.
    try:
        real_time = float(toks[1])
        real_unit = toks[2]
        cpu_time = float(toks[3])
        cpu_unit = toks[4]
        iterations = int(toks[5])
    except ValueError:
        return None
    if real_unit not in _TIME_UNITS or cpu_unit not in _TIME_UNITS:
        return None

    # Strip the `/iterations:N` suffix Google Benchmark adds when the
    # benchmark was registered via ->Iterations(N); the parsed name
    # should match what the test was registered as.
    if "/iterations:" in name:
        name = name.split("/iterations:", 1)[0]

    metrics: list[dict] = [
        {"name": "real_time", "unit": real_unit,
         "value": real_time, "direction": "lower_is_better"},
        {"name": "cpu_time", "unit": cpu_unit,
         "value": cpu_time, "direction": "lower_is_better"},
    ]
    for counter_tok in toks[6:]:
        parsed = _parse_counter(counter_tok)
        if parsed is not None:
            metrics.append(parsed)

    return {
        "test_name": name,
        "iterations": iterations,
        "metrics": metrics,
    }


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    # Strip BOM if present (GH Actions logs arrive with one).
    if content.startswith("\ufeff"):
        content = content[1:]

    lines = [_strip_gh_prefix(ln.rstrip("\r\n"))
             for ln in content.splitlines()]

    out: list[dict] = []
    executable: str | None = None
    header_seen = False
    in_table = False

    for line in lines:
        # New block: `Running ./<path>` resets parser state.
        m = _RUNNING.match(line)
        if m:
            executable = m.group(1)
            header_seen = False
            in_table = False
            continue
        if _HEADER.match(line):
            header_seen = True
            continue
        if _SEPARATOR.match(line):
            # Google Benchmark's layout is separator → header → separator
            # → rows. The second separator (the one we see after the
            # header) opens the data region.
            if header_seen:
                in_table = True
            continue
        if not in_table:
            continue
        row = _parse_row(line)
        if row is None:
            # Malformed row or a trailing banner line; skip without
            # closing the table so a brief blank line doesn't end the run.
            continue
        sut = {}
        if executable:
            sut["name"] = executable
        entry: dict = {
            "test": {"test_name": row["test_name"]},
            "run": {"passed": True},
            "env": {"framework": {"name": "google-benchmark"}},
            "metrics": row["metrics"],
        }
        if sut:
            entry["sut"] = sut
        if row["iterations"]:
            entry["extra_info"] = {"iterations": row["iterations"]}
        out.append(entry)

    return out
