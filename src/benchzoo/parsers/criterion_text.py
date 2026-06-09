"""Parser for criterion's default human-readable stdout.

Unlike ``--output-format bencher`` (see :mod:`criterion_bencher`),
criterion's *default* output prints, per benchmark, an id line followed
by a ``time:`` confidence-interval line::

    FTS Cold Query/cold_query/1000_rows
                            time:   [214.98 µs 215.90 µs 217.69 µs]

The three bracketed values are ``[lower_bound, point_estimate,
upper_bound]``; we report the point estimate as the benchmark's time and
keep the bounds as extra metrics.

Two things make this format awkward, both handled here:

1. **The unit auto-scales** (ns / µs / ms / s) per benchmark — and even
   per run as timings drift — so a raw value is meaningless without its
   unit. We normalise every value to **nanoseconds** for a stable,
   comparable metric.
2. **It's usually buried in a much larger CI log** (cargo compile output,
   "Benchmarking …: Warming up", outlier notes). We scan the whole
   content for ``time:`` lines and read the id from the line just above,
   ignoring everything else — the "find an anchor line, then read the
   neighbouring line" strategy.

See ``frameworks/language/criterion/README.md``.
"""

from __future__ import annotations

import re


# Strip ANSI escape codes (cargo colorizes output even when piped to a file).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Nanoseconds per criterion time unit. µ may be the micro sign (U+00B5) or
# Greek mu (U+03BC); criterion also occasionally emits ASCII "us". Fast
# benches measure in picoseconds (criterion divides wall time by a huge
# iteration count), so "ps" is real and must be handled.
_UNIT_NS = {"ps": 1e-3, "ns": 1.0, "µs": 1e3, "μs": 1e3, "us": 1e3,
            "ms": 1e6, "s": 1e9}
_UNIT = r"(?:ps|ns|µs|μs|us|ms|s)"

# The criterion confidence-interval line: "time:   [lo <u> mid <u> hi <u>]".
# criterion prints the benchmark id INLINE on this line for short names
# ("benchmark1              time:   [...]") and on its OWN line just above
# when the id is long enough to wrap. So capture an optional id before
# "time:" here, and fall back to the preceding line when it's absent.
_TIME_RE = re.compile(
    r"^(?P<name>.*?)\btime:\s*\[\s*"
    r"([0-9.]+)\s*(" + _UNIT + r")\s+"
    r"([0-9.]+)\s*(" + _UNIT + r")\s+"
    r"([0-9.]+)\s*(" + _UNIT + r")\s*\]"
)

# Lines that are criterion/cargo chrome — never a benchmark id.
_NOISE_PREFIXES = (
    "Benchmarking", "Found ", "Gnuplot", "Running", "warning:", "change:",
    "time:", "thrpt:", "slope", "mean", "median", "std. dev.", "MAD", "R^2",
    "Compiling", "Finished", "Updating", "Downloading", "Compl",
)


def _to_ns(value: str, unit: str) -> float:
    return float(value) * _UNIT_NS[unit]


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    lines = [_ANSI_RE.sub("", ln) for ln in content.splitlines()]

    out: list[dict] = []
    for i, line in enumerate(lines):
        m = _TIME_RE.match(line)
        if not m:
            continue
        # Inline id (short names): everything before "time:" on this line.
        name = m.group("name").strip()
        if not name or name.startswith(_NOISE_PREFIXES):
            # Wrapped id (long names): the nearest preceding non-blank line
            # that isn't criterion/cargo chrome.
            name = None
            for j in range(i - 1, max(-1, i - 6), -1):
                cand = lines[j].strip()
                if not cand or cand.startswith(_NOISE_PREFIXES):
                    continue
                name = cand
                break
        if not name:
            continue
        vals = m.groups()[1:]   # the six (value, unit) groups after "name"
        lower = _to_ns(vals[0], vals[1])
        point = _to_ns(vals[2], vals[3])
        upper = _to_ns(vals[4], vals[5])
        out.append({
            "test": {"test_name": name},
            "run": {"passed": True},
            "env": {"framework": {"name": "criterion"}},
            "metrics": [
                {"name": "time", "unit": "ns", "value": point,
                 "direction": "lower_is_better"},
                {"name": "time_lower_bound", "unit": "ns", "value": lower,
                 "direction": "lower_is_better"},
                {"name": "time_upper_bound", "unit": "ns", "value": upper,
                 "direction": "lower_is_better"},
            ],
        })
    return out
