"""Parser for mitata's default human-readable console table.

mitata is a *library*, not a runner: by default ``run()`` prints a
formatted, ANSI-coloured table to stdout (``run({ json: true })``
instead returns the structured object handled by :mod:`mitata`). The
console table is the format a developer sees in their terminal and the
one a CI job prints to its log when it does not capture JSON. It looks
like::

    clk: ~3.33 GHz
    cpu: Intel(R) Xeon(R) Platinum 8370C CPU @ 2.80GHz
    runtime: node 20.20.2 (x64-linux)

    benchmark                   avg (min … max) p75 / p99    (min … top 1%)
    ------------------------------------------- -------------------------------
    benchmark1                      2.15 s/iter    2.15 s   █              █ █
                              (2.15 s … 2.15 s)    2.15 s ▅ █    ▅        ▅█▅█▅
                        (  3.80 kb … 204.78 kb)  87.23 kb █▁█▁▁▁▁█▁▁▁▁▁▁▁▁█████

    benchmark2                   467.73 ns/iter 449.51 ns █
                        (446.25 ns … 630.90 ns) 627.97 ns █
                        (  0.16  b … 139.53  b)   0.69  b █▄▂▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▂▃

Each benchmark occupies three rows. The **first** row carries the
benchmark name plus ``<avg> <unit>/iter`` (the headline average) and the
``p75`` value. The second row holds ``(min … max)`` and ``p99``; the
third holds the per-iteration memory band. We report the **avg** as the
benchmark's ``time`` metric and the ``min``/``max`` from the second row
as extra metrics, all normalised to **nanoseconds** (mitata auto-scales
the displayed unit per benchmark: ns / µs / ms / s).

This parser tolerates:

* the GitHub Actions log ISO-8601 timestamp prefix on every line,
* ANSI colour codes (mitata colourises even when piped),
* the unicode ellipsis ``…`` (U+2026) and the micro sign ``µ``/``μ``.

See ``frameworks/language/mitata/README.md``.
"""

from __future__ import annotations

import re


# Strip ANSI escape codes (mitata colourises its table even when piped).
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

# GitHub Actions prefixes every log line with an ISO-8601 timestamp and a
# space, e.g. "2026-06-03T18:33:42.2759200Z ". Tolerate (strip) it.
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\s")

# Nanoseconds per mitata time unit. mitata renders ps/ns/µs/ms/s; µ may be
# the micro sign (U+00B5) or Greek mu (U+03BC).
_UNIT_NS = {"ps": 1e-3, "ns": 1.0, "µs": 1e3, "μs": 1e3, "us": 1e3,
            "ms": 1e6, "s": 1e9}
_UNIT = r"(?:ps|ns|µs|μs|us|ms|s)"

# The benchmark name row: "<name>  <avg> <unit>/iter  <p75> <unit> <hist>".
# The ".../iter" suffix is the load-bearing anchor — only the headline row
# carries it, never the "(min … max)" or memory rows.
_NAME_RE = re.compile(
    r"^(?P<name>\S.*?)\s+"
    r"(?P<avg>[0-9][0-9.,]*)\s*(?P<aunit>" + _UNIT + r")/iter\b"
)

# The second ("(min … max)") row: "(  2.15 s … 2.15 s)  <p99> <unit> <hist>".
# … is the unicode ellipsis (U+2026); a literal "..." is tolerated too.
_RANGE_RE = re.compile(
    r"^\(\s*(?P<min>[0-9][0-9.,]*)\s*(?P<munit>" + _UNIT + r")\s*"
    r"(?:…|\.\.\.)\s*"
    r"(?P<max>[0-9][0-9.,]*)\s*(?P<xunit>" + _UNIT + r")\s*\)"
)


def _strip(line: str) -> str:
    line = _ANSI_RE.sub("", line)
    line = _TS_RE.sub("", line)
    return line


def _to_ns(value: str, unit: str) -> float:
    return float(value.replace(",", "")) * _UNIT_NS[unit]


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    lines = [_strip(ln) for ln in content.splitlines()]

    out: list[dict] = []
    for i, line in enumerate(lines):
        m = _NAME_RE.match(line)
        if not m:
            continue
        name = m.group("name").strip()
        # Guard against the header row ("benchmark   avg (min … max) ...")
        # and divider lines.
        if not name or name == "benchmark" or set(name) <= {"-", " "}:
            continue

        avg_ns = _to_ns(m.group("avg"), m.group("aunit"))

        metrics: list[dict] = [
            {"name": "time", "unit": "ns", "value": avg_ns,
             "direction": "lower_is_better"},
        ]

        # The min/max range is on the very next non-empty line.
        for j in range(i + 1, min(len(lines), i + 3)):
            rm = _RANGE_RE.match(lines[j].lstrip())
            if rm:
                metrics.append({
                    "name": "min", "unit": "ns",
                    "value": _to_ns(rm.group("min"), rm.group("munit")),
                    "direction": "lower_is_better",
                })
                metrics.append({
                    "name": "max", "unit": "ns",
                    "value": _to_ns(rm.group("max"), rm.group("xunit")),
                    "direction": "lower_is_better",
                })
                break

        out.append({
            "test": {"test_name": name},
            "run": {"passed": True},
            "env": {"framework": {"name": "mitata"}},
            "metrics": metrics,
        })

    return out
