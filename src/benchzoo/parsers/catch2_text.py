"""Parser for Catch2's default ``console`` reporter stdout.

Catch2 v3's *default* (human-readable) reporter prints, per benchmark, a
small fixed-width table. After a ``benchmark name … samples … iterations
… est run time`` header (and a ``mean / low mean / high mean`` and
``std dev / low std dev / high std dev`` legend), each benchmark emits
three data rows::

    benchmark name                       samples       iterations    est run time
                                         mean          low mean      high mean
                                         std dev       low std dev   high std dev
    -------------------------------------------------------------------------------
    benchmark1                                       3             1     6.45033 s
                                              2.1501 s      2.1501 s     2.15011 s
                                            4.94919 us    1.14881 us    5.42257 us

Row 1: ``<name> <samples> <iterations> <est_run_time> <unit>``.
Row 2: ``<mean> <unit> <low_mean> <unit> <high_mean> <unit>``  (the row we
report — the mean is the first value).
Row 3: ``<std_dev> <unit> <low_std_dev> <unit> <high_std_dev> <unit>``.

The unit auto-scales per benchmark (ns / us / ms / s), so a value is
meaningless without its unit; we normalise everything to **seconds**.

This block is usually buried in a much larger CI log (cmake configure +
compile noise), and when read from a GitHub Actions *job log* (rather than
the uploaded artifact) every line is prefixed with an ISO-8601 timestamp.
We tolerate that prefix and ANSI colour codes, and key off the data row
(name + an integer ``samples`` + integer ``iterations`` + a value+unit
``est run time``) so we never mistake a header or legend line for data.

Note: Catch2's ``--reporter xml`` (see :mod:`catch2_xml`) carries the same
statistics in a structured form; this parser exists for the case where only
the console stdout was captured. ``--reporter json`` / ``--reporter junit``
do **not** include benchmark statistics.

See ``frameworks/language/catch2/README.md``.
"""

from __future__ import annotations

import re


# Strip ANSI escape codes (CI logs are often colorized).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Optional GitHub-Actions per-line ISO-8601 timestamp prefix (present when
# the output is read from a job *log* rather than the uploaded artifact).
_TS = r"(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?"

# Catch2 time units -> seconds.
_UNIT_S = {
    "ps": 1e-12, "ns": 1e-9, "µs": 1e-6, "μs": 1e-6, "us": 1e-6,
    "ms": 1e-3, "s": 1.0,
}
_UNIT = r"(?:ps|ns|µs|μs|us|ms|s)"
_NUM = r"[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?"

# The benchmark *data* row:
#   "<name>   <samples:int>   <iterations:int>   <est_run_time> <unit>"
# The name may contain spaces, so anchor on the trailing
# "<int> <int> <num> <unit>" and capture the leading text as the name.
_DATA_RE = re.compile(
    r"^\s*" + _TS + r"(?P<name>\S.*?)\s+"
    r"(?P<samples>[0-9]+)\s+"
    r"(?P<iterations>[0-9]+)\s+"
    r"(?P<est>" + _NUM + r")\s+(?P<est_unit>" + _UNIT + r")\s*$"
)

# The mean row (immediately after the data row):
#   "<mean> <unit>   <low_mean> <unit>   <high_mean> <unit>"
_MEAN_RE = re.compile(
    r"^\s*" + _TS +
    r"(?P<mean>" + _NUM + r")\s+(?P<mean_unit>" + _UNIT + r")\s+"
    r"(?P<low>" + _NUM + r")\s+(?P<low_unit>" + _UNIT + r")\s+"
    r"(?P<high>" + _NUM + r")\s+(?P<high_unit>" + _UNIT + r")\s*$"
)

# Header/legend tokens that must never be read as a benchmark name.
_HEADER_WORDS = ("benchmark name", "samples", "iterations", "est run time")


def _to_s(value: str, unit: str) -> float:
    return float(value) * _UNIT_S[unit]


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    lines = [_ANSI_RE.sub("", ln) for ln in content.splitlines()]

    out: list[dict] = []
    for i, line in enumerate(lines):
        m = _DATA_RE.match(line)
        if not m:
            continue
        name = m.group("name").strip()
        # Reject the column header row ("benchmark name  samples …") — its
        # leading text is "benchmark name", not a real id.
        low = name.lower()
        if any(w in low for w in _HEADER_WORDS):
            continue

        metrics: list[dict] = [{
            "name": "est_run_time", "unit": "s",
            "value": _to_s(m.group("est"), m.group("est_unit")),
            "direction": "lower_is_better",
        }]

        # The mean row is the next non-empty line.
        for j in range(i + 1, min(len(lines), i + 4)):
            if not lines[j].strip():
                continue
            mm = _MEAN_RE.match(lines[j])
            if mm:
                metrics.insert(0, {
                    "name": "mean", "unit": "s",
                    "value": _to_s(mm.group("mean"), mm.group("mean_unit")),
                    "direction": "lower_is_better",
                })
                metrics.append({
                    "name": "mean_low", "unit": "s",
                    "value": _to_s(mm.group("low"), mm.group("low_unit")),
                    "direction": "lower_is_better",
                })
                metrics.append({
                    "name": "mean_high", "unit": "s",
                    "value": _to_s(mm.group("high"), mm.group("high_unit")),
                    "direction": "lower_is_better",
                })
            break

        out.append({
            "test": {"test_name": name, "params": {
                "samples": int(m.group("samples")),
                "iterations": int(m.group("iterations")),
            }},
            "run": {"passed": True},
            "env": {"framework": {"name": "catch2"}},
            "metrics": metrics,
        })

    return out
