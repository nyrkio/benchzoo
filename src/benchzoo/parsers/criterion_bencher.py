"""Parser for criterion's ``--output-format bencher`` text output.

This is the same wire format as Rust's older ``cargo bench`` / libtest
output, which is why parser-targets.md lists ``cargo bench`` as a
separate target whose parser *could* be shared with this one.

The format is one line per benchmark::

    test benchmark1 ... bench:  2150123486 ns/iter (+/- 10172)

with optional warnings and ANSI color codes from cargo's surrounding
output that we filter out.

Values are always in **nanoseconds** (``ns/iter``).

See ``frameworks/language/criterion/README.md``.
"""

from __future__ import annotations

import re


# Strip ANSI escape codes (cargo colorizes its output even when piped).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Example lines (criterion and libtest emit the same wire format, but
# nightly cargo bench / libtest adds thousands separators and decimals):
#   test benchmark1 ... bench:  2150123486 ns/iter (+/- 10172)          # criterion
#   test benchmark1 ... bench:  2,150,112,915.10 ns/iter (+/- 17,654.01)  # libtest
_BENCH_RE = re.compile(
    r"^test\s+(\S+)\s+\.\.\.\s+bench:\s+"
    r"([0-9,]+(?:\.[0-9]+)?)\s+ns/iter\s+"
    r"\(\+/-\s+([0-9,]+(?:\.[0-9]+)?)\)\s*$"
)


def _parse_ns(raw: str) -> float:
    """Handle both plain ``2150123486`` and ``2,150,112,915.10`` shapes."""
    return float(raw.replace(",", ""))


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    out: list[dict] = []
    for raw_line in content.splitlines():
        line = _ANSI_RE.sub("", raw_line).strip()
        m = _BENCH_RE.match(line)
        if not m:
            continue
        name = m.group(1)
        ns_per_iter = _parse_ns(m.group(2))
        deviation = _parse_ns(m.group(3))
        out.append({
            "timestamp": 0,
            "attributes": {"test_name": name},
            "metrics": [
                {
                    "name": "ns_per_iter",
                    "unit": "ns",
                    "value": ns_per_iter,
                    "direction": "lower_is_better",
                },
                {
                    "name": "deviation",
                    "unit": "ns",
                    "value": deviation,
                    "direction": "lower_is_better",
                },
            ],
            "passed": True,
        })

    return out
