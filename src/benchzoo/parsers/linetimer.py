"""Parser for the ``linetimer`` library's CodeTimer stdout.

linetimer (PyPI ``linetimer``) wraps a block in ``with CodeTimer('name'):``
and on exit prints one line per timed block::

    Code block 'Run polars query 1' took: 1.50120 s

We emit one benchmark per line: the quoted block name becomes the test
name and the elapsed time a single ``time`` metric. As with criterion's
text output, these lines are usually buried in a much larger CI log
(e.g. ``pola-rs/polars-benchmark`` times each TPC-H query this way, amid
cargo-compile and pytest noise), so we scan the whole content for
``Code block '…' took:`` lines and ignore everything else.

linetimer's default unit is *milliseconds*; callers can override it
(``pola-rs/polars-benchmark`` sets ``unit="s"`` for its TPC-H timings).
We normalise whatever unit it emits to seconds so the metric is
comparable across sources.
"""

from __future__ import annotations

import re


# Strip ANSI escapes (CI logs are often colorized).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# linetimer unit label -> seconds. linetimer's default label is "ms";
# polars-benchmark uses "s". Both (and the rest) normalise here.
_UNIT_S = {
    "ns": 1e-9, "µs": 1e-6, "μs": 1e-6, "us": 1e-6, "ms": 1e-3,
    "sec": 1.0, "s": 1.0, "min": 60.0, "m": 60.0, "h": 3600.0,
}
_UNIT = r"(?:ns|µs|μs|us|ms|sec|s|min|m|h)"

# Optional GitHub-Actions per-line ISO-8601 timestamp prefix. When the
# output is read from a job *log* (no benchmark artifact uploaded — e.g.
# pola-rs/polars-benchmark), every line is prefixed with one of these;
# artifact files are clean. Tolerate either.
_TS = r"(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?"

# "Code block 'NAME' took: 1.50120 s". A quoted name is required: linetimer
# only quotes when the block was named, and an anonymous block carries no
# useful test id.
_TOOK_RE = re.compile(
    r"^\s*" + _TS + r"Code block '([^']*)' took:\s*"
    r"([0-9.]+(?:[eE][+-]?[0-9]+)?)\s*(" + _UNIT + r")\b"
)


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    out: list[dict] = []
    for raw in content.splitlines():
        m = _TOOK_RE.match(_ANSI_RE.sub("", raw))
        if not m:
            continue
        name = m.group(1).strip()
        if not name:
            continue
        seconds = float(m.group(2)) * _UNIT_S[m.group(3)]
        out.append({
            "test": {"test_name": name},
            "run": {"passed": True},
            "env": {"framework": {"name": "linetimer"}},
            "metrics": [
                {"name": "time", "unit": "s", "value": seconds,
                 "direction": "lower_is_better"},
            ],
        })
    return out
