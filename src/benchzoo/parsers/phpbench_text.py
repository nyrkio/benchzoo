"""Parser for PHPBench's console ``aggregate`` report (plain text table).

When PHPBench runs with ``--report=aggregate`` and a text output (the
default console renderer), it prints an ASCII-art table, one row per
subject/variant::

    +-------------+-----------------+-----+------+-----+-----------+---------+--------+
    | benchmark   | subject         | set | revs | its | mem_peak  | mode    | rstdev |
    +-------------+-----------------+-----+------+-----+-----------+---------+--------+
    | SampleBench | benchBenchmark1 |     | 1    | 3   | 682.224kb | 2.150s  | ±0.00% |
    | SampleBench | benchBenchmark2 |     | 1000 | 5   | 682.224kb | 2.952μs | ±1.10% |
    | SampleBench | benchBenchmark3 |     | 10   | 5   | 1.934mb   | 3.704ms | ±0.74% |
    | SampleBench | benchBenchmark4 |     | 1    | 3   | 682.224kb | 1.150s  | ±0.00% |
    +-------------+-----------------+-----+------+-----+-----------+---------+--------+

The ``mode`` column is the headline per-revolution time and is
auto-scaled per row (``s`` / ``ms`` / ``μs`` / ``ns``), so a value is
meaningless without its unit — we normalise every ``mode`` to **seconds**
to match the XML parser and the rest of benchzoo.

``rstdev`` is the relative standard deviation, printed as ``±N.NN%``; we
emit it as a unitless metric.

Two things make this awkward, both handled here:

1. It is usually buried in a much larger CI log (composer install noise,
   "Dumped result to output.xml", the upload-artifact group), so we scan
   the whole content for table rows and ignore everything else.
2. When read from a GitHub Actions job *log* (no artifact uploaded) every
   line carries an ISO-8601 timestamp prefix; we tolerate it.

Subject names are PHPBench's ``benchBenchmark1`` convention; the parser
strips the ``bench`` prefix and lower-cases the first character —
``benchBenchmark1`` -> ``benchmark1`` — mirroring ``phpbench_xml``.

See ``frameworks/language/phpbench/README.md``.
"""

from __future__ import annotations

import re


# Strip ANSI escapes (CI logs are often colorized).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Optional GitHub-Actions per-line ISO-8601 timestamp prefix.
_TS = r"(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?"

# PHPBench time-unit label -> seconds. The console "mode" column auto-scales.
_UNIT_S = {
    "ns": 1e-9, "µs": 1e-6, "μs": 1e-6, "us": 1e-6,
    "ms": 1e-3, "s": 1.0,
}
_UNIT = r"(?:ns|µs|μs|us|ms|s)"

# A data row of the aggregate table:
#   | SampleBench | benchBenchmark1 | | 1 | 3 | 682.224kb | 2.150s | ±0.00% |
# Columns (pipe-delimited): benchmark, subject, set, revs, its, mem_peak,
# mode, rstdev. The header row (subject == "subject") is skipped by the
# _normalize_subject_name guard below.
_ROW_RE = re.compile(
    r"^\s*" + _TS + r"\|\s*(?P<benchmark>[^|]+?)\s*"
    r"\|\s*(?P<subject>[^|]+?)\s*"
    r"\|\s*(?P<set>[^|]*?)\s*"
    r"\|\s*(?P<revs>\d+)\s*"
    r"\|\s*(?P<its>\d+)\s*"
    r"\|\s*(?P<mem>[^|]*?)\s*"
    r"\|\s*(?P<mode>[0-9.]+)\s*(?P<modeunit>" + _UNIT + r")\s*"
    r"\|\s*(?:±)?(?P<rstdev>[0-9.]+)%?\s*"
    r"\|\s*$"
)


def _normalize_subject_name(raw: str) -> str:
    """``benchBenchmark1`` -> ``benchmark1``."""
    if raw.startswith("bench"):
        tail = raw[len("bench"):]
        return tail[:1].lower() + tail[1:] if tail else tail
    return raw


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    lines = [_ANSI_RE.sub("", ln) for ln in content.splitlines()]

    out: list[dict] = []
    for line in lines:
        m = _ROW_RE.match(line)
        if not m:
            continue
        raw_subject = m.group("subject")
        # Skip the header row ("subject") and any non-bench rows.
        if not raw_subject.startswith("bench"):
            continue
        test_name = _normalize_subject_name(raw_subject)

        mode_s = float(m.group("mode")) * _UNIT_S[m.group("modeunit")]
        metrics = [
            {"name": "mode", "unit": "s", "value": mode_s,
             "direction": "lower_is_better"},
        ]
        try:
            metrics.append({
                "name": "rstdev", "unit": "%",
                "value": float(m.group("rstdev")),
                "direction": "lower_is_better",
            })
        except (TypeError, ValueError):
            pass

        extra_info: dict = {
            "revs": int(m.group("revs")),
            "iterations": int(m.group("its")),
        }

        out.append({
            "test": {"test_name": test_name},
            "run": {"passed": True},
            "env": {"framework": {"name": "phpbench"}},
            "metrics": metrics,
            "extra_info": extra_info,
        })

    return out
