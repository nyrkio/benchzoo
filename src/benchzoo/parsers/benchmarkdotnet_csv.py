"""Parser for BenchmarkDotNet's ``[CsvExporter]`` output.

The CSV is a flat table, one row per benchmark. It has a LOT of
columns — most are configuration (Jit, Platform, Affinity, Runtime,
…) — but the numeric stats we care about are in these columns::

    Method, Mean, Error, StdDev, Median

BenchmarkDotNet renders these values as **localized strings with unit
suffixes**, e.g.::

    Mean           Error       StdDev    Median
    "2,150,230.74 μs"  "3,407.92 μs"  186.80 μs   "2,150,123.069 μs"

Numbers may be quoted if they contain thousands separators; the unit
suffix (``ns``, ``μs``, ``ms``, ``s``) varies per row depending on
magnitude. The parser strips commas, parses the float, and converts
to nanoseconds for internal consistency with the JSON parser.

test_name is normalized from ``Method`` (``"Benchmark1"`` →
``"benchmark1"``).

See ``frameworks/language/benchmarkdotnet/README.md``.
"""

from __future__ import annotations

import csv
import io
import re


_VALUE_RE = re.compile(
    r"^\s*([0-9,]+(?:\.[0-9]+)?)\s*(ns|us|\u00b5s|\u03bcs|ms|s)\s*$"
)
# Two variants of "μ" exist in the wild: U+00B5 MICRO SIGN and U+03BC
# GREEK SMALL LETTER MU. BenchmarkDotNet uses U+03BC; handle both to
# be safe.

_TO_NS = {
    "ns": 1.0,
    "us": 1_000.0,
    "\u00b5s": 1_000.0,
    "\u03bcs": 1_000.0,
    "ms": 1_000_000.0,
    "s": 1_000_000_000.0,
}


def _parse_ns(raw: str) -> float:
    """Turn BenchmarkDotNet's ``"2,150,230.74 μs"`` into nanoseconds."""
    m = _VALUE_RE.match(raw)
    if not m:
        raise ValueError(f"unparseable BDN CSV value: {raw!r}")
    number = float(m.group(1).replace(",", ""))
    unit = m.group(2)
    return number * _TO_NS[unit]


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    out: list[dict] = []
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        method = row.get("Method", "")
        test_name = method[:1].lower() + method[1:] if method else ""

        metrics = [
            {"name": "mean",   "unit": "ns", "value": _parse_ns(row["Mean"]),   "direction": "lower_is_better"},
            {"name": "stddev", "unit": "ns", "value": _parse_ns(row["StdDev"]), "direction": "lower_is_better"},
            {"name": "median", "unit": "ns", "value": _parse_ns(row["Median"]), "direction": "lower_is_better"},
            {"name": "error",  "unit": "ns", "value": _parse_ns(row["Error"]),  "direction": "lower_is_better"},
        ]
        out.append({
            "timestamp": 0,
            "attributes": {"test_name": test_name},
            "metrics": metrics,
            "passed": True,
        })

    return out
