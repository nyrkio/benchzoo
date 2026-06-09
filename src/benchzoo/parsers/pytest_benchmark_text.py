"""Parser for pytest-benchmark's terminal results table (stdout).

pytest-benchmark prints a per-group ASCII table at the end of a run, e.g.::

    --------------------- benchmark 'sleep': 2 tests ---------------------
    Name (time in s)        Min               Max              Mean   ...
    ----------------------------------------------------------------------
    test_benchmark4      1.1501 (1.0)      1.1502 (1.0)      1.1501 (1.0)  ...
    test_benchmark1      2.1501 (1.87)     2.1501 (1.87)     2.1501 (1.87) ...
    ----------------------------------------------------------------------

This is the same data the ``--benchmark-json`` parser reads, but captured
from the console/CI log rather than the JSON artifact. We parse it because a
project may print this table to its CI stdout without uploading the JSON.

Three things make this format awkward, all handled here:

1. **The unit is declared per table**, in the ``Name (time in <unit>)``
   header line — not on each value. pytest-benchmark auto-scales the unit
   per group (``us`` for the fast ``compute`` group, ``s`` for the
   ``sleep`` group), so each table can use a different unit. We read the
   header to learn the column unit, then carry it down to the rows under
   it. We normalise every timing to **seconds** so metrics are comparable.

2. **Each value carries a ``(ratio)`` annotation** — the normalised ratio
   vs. the fastest row (``(1.0)`` for the best). We discard it. Values may
   also carry **thousands separators** (``3,190.5690``) which we strip.

3. **It is usually buried in a much larger CI/pytest log** and, when read
   from a GitHub Actions *log*, every line carries an ISO-8601 timestamp
   prefix. We scan the whole content, track the current table's unit from
   the most recent ``Name (time in …)`` header, and tolerate the prefix
   and ANSI codes.

The fixed columns are, in order:
``Name  Min  Max  Mean  StdDev  Median  IQR  Outliers  OPS  Rounds  Iterations``.
``Outliers`` is ``N;M`` (not a timing); ``OPS`` is operations/second
(higher_is_better); ``Rounds``/``Iterations`` are integer counts. The test
name has its ``test_`` prefix stripped to match the JSON parser
(``test_benchmark1`` -> ``benchmark1``).

See ``frameworks/language/pytest-benchmark/README.md``.
"""

from __future__ import annotations

import re


# Strip ANSI escape codes (pytest colorizes its terminal output).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Optional GitHub-Actions per-line ISO-8601 timestamp prefix (present when
# the table is read from a job log rather than a clean artifact).
_TS = r"(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?"

# Time-unit label -> seconds. pytest-benchmark renders ns/us/ms/s.
_UNIT_S = {
    "ns": 1e-9, "µs": 1e-6, "μs": 1e-6, "us": 1e-6, "ms": 1e-3, "s": 1.0,
}
_UNIT = r"(?:ns|µs|μs|us|ms|s)"

# The per-table header line that declares the column unit:
#   "Name (time in s)   Min   Max   ..."
_HEADER_RE = re.compile(
    r"^\s*" + _TS + r"Name \(time in (?P<unit>" + _UNIT + r")\)\s+Min\b"
)

# A number, optionally with thousands separators: 1.1501 or 3,190.5690.
_NUM = r"[0-9][0-9,]*(?:\.[0-9]+)?"

# A data row: the test name, then six timing columns each shaped
# "<num> (<ratio>)", then "Outliers" (N;M), then "OPS <num> (<ratio>)",
# then Rounds and Iterations. We only need Name, the six timings, and OPS,
# so capture those (by name, since the timestamp prefix and the per-value
# "(ratio)" annotations make positional groups error-prone) and skip the
# rest loosely.
def _val(tag: str) -> str:
    return r"(?P<" + tag + r">" + _NUM + r")\s*\([^)]*\)"


_ROW_RE = re.compile(
    r"^\s*" + _TS +
    r"(?P<name>\S+)\s+" +
    _val("mn") + r"\s+" +    # Min
    _val("mx") + r"\s+" +    # Max
    _val("mean") + r"\s+" +  # Mean
    _val("std") + r"\s+" +   # StdDev
    _val("med") + r"\s+" +   # Median
    _val("iqr") + r"\s+" +   # IQR
    r"\d+;\d+\s+" +          # Outliers (N;M)
    r"(?P<ops>" + _NUM + r")\s*\([^)]*\)"  # OPS
)


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    out: list[dict] = []
    seen: set[str] = set()
    unit = "s"  # carried down from the most recent table header
    for raw in content.splitlines():
        line = _ANSI_RE.sub("", raw)

        h = _HEADER_RE.match(line)
        if h:
            unit = h.group("unit")
            continue

        m = _ROW_RE.match(line)
        if not m:
            continue
        name = m.group("name")
        # Rows always start with a real test name; the table is small and a
        # name must look like an identifier (pytest test ids do).
        if not re.fullmatch(r"[A-Za-z_][\w\[\]:.\-]*", name):
            continue

        scale = _UNIT_S[unit]
        mn = _num(m.group("mn")) * scale
        mx = _num(m.group("mx")) * scale
        mean = _num(m.group("mean")) * scale
        std = _num(m.group("std")) * scale
        med = _num(m.group("med")) * scale
        ops = _num(m.group("ops"))

        test_name = name[5:] if name.startswith("test_") else name
        # A test appears once per table; if the same table is printed twice
        # in one log (e.g. two pytest invocations), keep the first.
        if test_name in seen:
            continue
        seen.add(test_name)

        out.append({
            "test": {"test_name": test_name},
            "run": {"passed": True},
            "env": {"framework": {"name": "pytest-benchmark"}},
            "metrics": [
                {"name": "mean", "unit": "s", "value": mean,
                 "direction": "lower_is_better"},
                {"name": "min", "unit": "s", "value": mn,
                 "direction": "lower_is_better"},
                {"name": "max", "unit": "s", "value": mx,
                 "direction": "lower_is_better"},
                {"name": "stddev", "unit": "s", "value": std,
                 "direction": "lower_is_better"},
                {"name": "median", "unit": "s", "value": med,
                 "direction": "lower_is_better"},
                {"name": "ops", "unit": "ops/s", "value": ops,
                 "direction": "higher_is_better"},
            ],
        })
    return out
