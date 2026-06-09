"""Parser for hyperfine's human-readable stdout summary.

When a project runs ``hyperfine`` in CI without uploading the
``--export-json``/``--export-csv`` artifact, the only record of the
results is the tool's default *console* output, captured in the job log.
hyperfine prints, per benchmarked command, a three-line block::

    Benchmark 1: benchmark1
      Time (mean ± σ):      2.153 s ±  0.000 s    [User: 0.001 s, System: 0.003 s]
      Range (min … max):    2.153 s …  2.154 s    10 runs

We anchor on the ``Benchmark N: <name>`` header (the name is whatever was
passed via ``--command-name``, else the raw shell string), then read the
following ``Time (mean ± σ):`` and ``Range (min … max):`` lines to recover
mean, stddev, user, system, min and max. The stdout block has **no
median** (that only appears in the JSON/CSV exports), so this format is
slightly lossier than :mod:`hyperfine_json` / :mod:`hyperfine_csv`.

Two things make the console format awkward, both handled here:

1. **The unit auto-scales** per benchmark (s / ms / µs / ns) — a fast
   command reports ``2.9 ms`` while a slow one reports ``2.153 s``. Every
   value is normalised to **seconds** so the metric is comparable.
2. **It is buried in a much larger CI log** (apt noise, ``##[group]``
   markers, a trailing ``Summary`` / "N times faster" block, and — when
   read from a GitHub Actions *log* rather than a clean terminal — an
   ISO-8601 timestamp prefix on every line plus ANSI colour codes). We
   scan the whole content, tolerate the prefix and ANSI codes, and ignore
   everything that is not a benchmark block.

All hyperfine values are durations, so ``direction`` is always
``"lower_is_better"``. See ``frameworks/generic/hyperfine/README.md``.
"""

from __future__ import annotations

import re


# Strip ANSI escape codes (hyperfine colorizes; GH logs may keep them).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Optional GitHub-Actions per-line ISO-8601 timestamp prefix. Present when
# the output is read from a job *log* (no artifact uploaded); absent in a
# clean terminal capture. Tolerate either.
_TS = r"(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?"

# Seconds per hyperfine time unit. µ may be the micro sign (U+00B5) or
# Greek mu (U+03BC); hyperfine also emits scaled units down to ns.
_UNIT_S = {"ns": 1e-9, "µs": 1e-6, "μs": 1e-6, "us": 1e-6, "ms": 1e-3, "s": 1.0}
_UNIT = r"(?:ns|µs|μs|us|ms|s)"

# "Benchmark 1: benchmark1" — the per-command header. The number is just a
# display index; the part after the colon is the test name.
_HEADER_RE = re.compile(r"^\s*" + _TS + r"Benchmark\s+\d+:\s*(?P<name>.+?)\s*$")

# "  Time (mean ± σ):      2.153 s ±  0.000 s    [User: 0.001 s, System: 0.003 s]"
# The "±" between mean and stddev is U+00B1; "σ" is U+03C3.
_VAL = r"([0-9.]+)\s*(" + _UNIT + r")"
_TIME_RE = re.compile(
    r"^\s*" + _TS + r"\s*Time\s*\(mean.*?\):\s*"
    + _VAL + r"\s*[±+]\s*" + _VAL
    + r"\s*\[User:\s*" + _VAL + r",\s*System:\s*" + _VAL + r"\]"
)

# "  Range (min … max):    2.153 s …  2.154 s    10 runs"
# The "…" between min and max is U+2026 (ellipsis).
_RANGE_RE = re.compile(
    r"^\s*" + _TS + r"\s*Range\s*\(min.*?max\):\s*"
    + _VAL + r"\s*(?:…|\.\.\.)\s*" + _VAL
)


def _to_s(value: str, unit: str) -> float:
    return float(value) * _UNIT_S[unit]


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    lines = [_ANSI_RE.sub("", ln) for ln in content.splitlines()]

    out: list[dict] = []
    i = 0
    n = len(lines)
    while i < n:
        header = _HEADER_RE.match(lines[i])
        if not header:
            i += 1
            continue
        name = header.group("name").strip()

        # Look ahead a few lines for the Time and Range lines belonging to
        # this benchmark. hyperfine may interleave blank lines and a
        # "Warning:" line; stop if we hit the next benchmark header.
        mean = stddev = user = system = mn = mx = None
        j = i + 1
        while j < n and j < i + 8:
            if _HEADER_RE.match(lines[j]):
                break
            tm = _TIME_RE.match(lines[j])
            if tm:
                mean = _to_s(tm.group(1), tm.group(2))
                stddev = _to_s(tm.group(3), tm.group(4))
                user = _to_s(tm.group(5), tm.group(6))
                system = _to_s(tm.group(7), tm.group(8))
                j += 1
                continue
            rng = _RANGE_RE.match(lines[j])
            if rng:
                mn = _to_s(rng.group(1), rng.group(2))
                mx = _to_s(rng.group(3), rng.group(4))
            j += 1

        if mean is None:
            # A header with no parseable Time line — skip it (not a real
            # hyperfine result block).
            i += 1
            continue

        metrics = [{"name": "mean", "unit": "s", "value": mean,
                    "direction": "lower_is_better"}]
        if stddev is not None:
            metrics.append({"name": "stddev", "unit": "s", "value": stddev,
                            "direction": "lower_is_better"})
        if mn is not None:
            metrics.append({"name": "min", "unit": "s", "value": mn,
                            "direction": "lower_is_better"})
        if mx is not None:
            metrics.append({"name": "max", "unit": "s", "value": mx,
                            "direction": "lower_is_better"})
        if user is not None:
            metrics.append({"name": "user", "unit": "s", "value": user,
                            "direction": "lower_is_better"})
        if system is not None:
            metrics.append({"name": "system", "unit": "s", "value": system,
                            "direction": "lower_is_better"})

        out.append({
            "test": {"test_name": name},
            "run": {"passed": True},
            "env": {"framework": {"name": "hyperfine"}},
            "metrics": metrics,
        })
        i = j
    return out
