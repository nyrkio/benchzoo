"""Parser for benchmark-ips's default human-readable stdout.

benchmark-ips (the standard Ruby micro-benchmarking library) prints a
two-section console report. The first ("Warming up") section is calibration
noise; the load-bearing section is "Calculating", which emits one line per
report::

    Calculating -------------------------------------
              benchmark1      0.465 (± 0.0%) i/s     (2.15 s/i) -      1.000 in   2.150126s
              benchmark2     23.254k (± 0.5%) i/s   (43.00 μs/i) -     48.804k in   2.098763s
              benchmark3    232.857 (± 4.7%) i/s    (4.29 ms/i) -    484.000 in   2.083193s
              benchmark4      0.869 (± 0.0%) i/s     (1.15 s/i) -      2.000 in   2.300269s

Each line carries:

- the report label (``benchmark1`` .. ``benchmark4``) — maps directly to
  the test name;
- the throughput in **iterations per second** (``i/s``), with a ``k``/``M``
  SI suffix for large numbers (``23.254k`` = 23254.0). Higher is better.
- the **time per iteration** in parentheses (``2.15 s/i``, ``43.00 μs/i``,
  ``4.29 ms/i``) whose unit auto-scales (s / ms / µs / ns). Lower is better.
  This is the metric that carries the canonical sample's wall-time ground
  truth (benchmark1 ≈ 2.15 s/i, benchmark4 ≈ {1.15, 2.15, 3.15} s/i).
- the ``± X%`` standard deviation of the ips number.

Two things make this awkward, both handled here:

1. **Auto-scaling units** on the per-iteration time and an SI suffix on the
   ips number — we normalise the per-iteration time to **seconds** and the
   ips number to plain iterations/second.
2. **It's usually buried in a CI log** with an ISO-8601 timestamp prefix on
   every line (GitHub Actions) plus ANSI colour codes. We strip both and
   scan the whole content for the "Calculating" data lines, ignoring the
   "Warming up" and "Comparison" sections (whose lines have a different
   shape).

See ``frameworks/language/benchmark-ips/README.md``.
"""

from __future__ import annotations

import re


# Strip ANSI escape codes.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Strip the GitHub Actions ISO-8601 timestamp prefix, e.g.
# "2026-06-05T09:25:54.3211064Z ".
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s")

# Seconds per benchmark-ips time-per-iteration unit. µ may be the micro sign
# (U+00B5) or Greek mu (U+03BC).
_UNIT_S = {"ns": 1e-9, "µs": 1e-6, "μs": 1e-6, "us": 1e-6, "ms": 1e-3, "s": 1.0}
_UNIT = r"(?:ns|µs|μs|us|ms|s)"

# SI multipliers on the ips headline number.
_SI = {"": 1.0, "k": 1e3, "M": 1e6, "B": 1e9}

# A "Calculating" data line:
#   <label>  <ips><si> (± <sd>%) i/s   (<per_iter> <unit>/i) - <iters> in <wall>s
# The "(.../i)" per-iteration block is the marker that distinguishes these
# data lines from the "Warming up" (".. i/100ms") and "Comparison" lines.
_LINE_RE = re.compile(
    r"^(?P<name>\S+)\s+"
    r"(?P<ips>[0-9.]+)(?P<ips_si>[kMB]?)\s*"
    r"\(±\s*(?P<sd>[0-9.]+)%\)\s*i/s\s+"
    r"\(\s*(?P<per>[0-9.]+)\s*(?P<perunit>" + _UNIT + r")/i\s*\)"
)


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    out: list[dict] = []
    for raw in content.splitlines():
        line = _TS_RE.sub("", raw)
        line = _ANSI_RE.sub("", line).strip()
        m = _LINE_RE.match(line)
        if not m:
            continue
        ips = float(m.group("ips")) * _SI[m.group("ips_si")]
        per_iter_s = float(m.group("per")) * _UNIT_S[m.group("perunit")]
        sd_pct = float(m.group("sd"))
        out.append({
            "test": {"test_name": m.group("name")},
            "run": {"passed": True},
            "env": {"framework": {"name": "benchmark-ips"}},
            "metrics": [
                {"name": "ips", "unit": "iterations/second", "value": ips,
                 "direction": "higher_is_better"},
                {"name": "time_per_iteration", "unit": "s", "value": per_iter_s,
                 "direction": "lower_is_better"},
                {"name": "ips_stddev_pct", "unit": "%", "value": sd_pct,
                 "direction": "lower_is_better"},
            ],
        })
    return out
