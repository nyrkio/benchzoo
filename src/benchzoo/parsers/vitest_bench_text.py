"""Parser for vitest ``bench`` mode's default-reporter stdout table.

When ``vitest bench --run`` runs with the *default* (or *verbose*)
reporter — the only reporters bench mode supports — it prints a
tinybench results table to the console, one row per ``bench(...)``
call::

       name        hz       min       max      mean       p75       p99      p995      p999     rme  samples
     · benchmark1      0.4646  2,152.23  2,152.40  2,152.34  2,152.40  2,152.40  2,152.40  2,152.40  ±0.01%        3  slowest
     · benchmark2  124,736.49    0.0068    0.3558    0.0080    0.0069    0.0390    0.0695    0.0903  ±0.71%    62369  fastest
     · benchmark3    3,440.62    0.0301    5.1278    0.2906    0.6026    2.8629    3.1719    4.7152  ±7.42%     1722
     · benchmark4      0.8688  1,150.39  1,151.42  1,151.06  1,151.42  1,151.42  1,151.42  1,151.42  ±0.13%        3

Each data row begins with a ``·`` (U+00B7) bullet, then the bench
name, then eleven columns: ``hz min max mean p75 p99 p995 p999 rme
samples`` and an optional trailing ``fastest``/``slowest`` tag.

**Units:** ``hz`` is operations per second (higher is better); every
time column (``min``/``max``/``mean``/``p75``/``p99``/``p995``/``p999``)
is **milliseconds** — tinybench's default — and lower is better. Numbers
use comma thousands separators (``2,152.34``, ``124,736.49``). ``rme``
is the relative margin of error, printed as ``±0.71%``.

This block is usually buried in a much larger CI log: npm-install
noise, the vitest "experimental feature" banner, a ``BENCH Summary``
section, etc. When read from a GitHub-Actions *job log* (rather than a
clean artifact) every line is also prefixed with an ISO-8601 timestamp
and colorized with ANSI escapes. We strip the ANSI codes, tolerate the
timestamp, and scan for the ``·``-prefixed rows, ignoring everything
else. The header row is *not* required — we key off the bullet.

See ``frameworks/language/vitest-bench/README.md``.
"""

from __future__ import annotations

import re


# Strip ANSI escape codes (vitest colorizes the table even when piped).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Optional GitHub-Actions per-line ISO-8601 timestamp prefix. Present when
# the output is read from a job *log* (this framework only uploads the
# JSON artifact, so the console table is only ever seen via the log).
_TS = r"(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?"

# A number with optional comma thousands separators and a decimal part,
# e.g. "0.0068", "2,152.34", "124,736.49".
_NUM = r"[0-9][0-9,]*(?:\.[0-9]+)?"

# A tinybench results row: a "·" bullet, the bench name, then the eleven
# columns (hz, 7 time columns, rme as ±x.xx%, samples), with an optional
# "fastest"/"slowest" tag at the end. The name is captured greedily up to
# the run of spaces before the first numeric (hz) column.
_ROW_RE = re.compile(
    r"^\s*" + _TS + r"\s*·\s+"
    r"(?P<name>\S.*?)\s{2,}"
    r"(?P<hz>"   + _NUM + r")\s+"
    r"(?P<min>"  + _NUM + r")\s+"
    r"(?P<max>"  + _NUM + r")\s+"
    r"(?P<mean>" + _NUM + r")\s+"
    r"(?P<p75>"  + _NUM + r")\s+"
    r"(?P<p99>"  + _NUM + r")\s+"
    r"(?P<p995>" + _NUM + r")\s+"
    r"(?P<p999>" + _NUM + r")\s+"
    r"\xb1?(?P<rme>" + _NUM + r")%\s+"
    r"(?P<samples>[0-9][0-9,]*)"
)


def _f(value: str) -> float:
    return float(value.replace(",", ""))


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    out: list[dict] = []
    for raw in content.splitlines():
        line = _ANSI_RE.sub("", raw)
        m = _ROW_RE.match(line)
        if not m:
            continue
        name = m.group("name").strip()
        if not name:
            continue
        out.append({
            "test": {"test_name": name},
            "run": {"passed": True},
            "env": {"framework": {"name": "vitest-bench"}},
            "metrics": [
                {"name": "mean",   "unit": "ms",    "value": _f(m.group("mean")), "direction": "lower_is_better"},
                {"name": "min",    "unit": "ms",    "value": _f(m.group("min")),  "direction": "lower_is_better"},
                {"name": "max",    "unit": "ms",    "value": _f(m.group("max")),  "direction": "lower_is_better"},
                {"name": "p75",    "unit": "ms",    "value": _f(m.group("p75")),  "direction": "lower_is_better"},
                {"name": "p99",    "unit": "ms",    "value": _f(m.group("p99")),  "direction": "lower_is_better"},
                {"name": "p995",   "unit": "ms",    "value": _f(m.group("p995")), "direction": "lower_is_better"},
                {"name": "p999",   "unit": "ms",    "value": _f(m.group("p999")), "direction": "lower_is_better"},
                {"name": "hz",     "unit": "ops/s", "value": _f(m.group("hz")),   "direction": "higher_is_better"},
                {"name": "rme",    "unit": "%",     "value": _f(m.group("rme"))},
            ],
            "extra_info": {"samples": int(m.group("samples").replace(",", ""))},
        })
    return out
