"""Parser for asv's human-readable ``asv run`` console output.

In addition to the per-commit results JSON (see :mod:`asv`), ``asv run``
streams a live progress table to stdout/stderr, one line per benchmark::

    · Running 4 total benchmarks (1 commits * 1 environments * 4 benchmarks)
    [ 0.00%] · For benchzoo commit c0c1d55c <main>:
    [ 0.00%] ·· Benchmarking virtualenv-py3.12
    [12.50%] ··· benchmarks.SampleBenchmark.time_benchmark1                 2.15±0s
    [25.00%] ··· benchmarks.SampleBenchmark.time_benchmark2                54.7±0μs
    [37.50%] ··· benchmarks.SampleBenchmark.time_benchmark3                5.02±0ms
    [50.00%] ··· benchmarks.SampleBenchmark.time_benchmark4                 1.15±0s

Each benchmark line carries:

- a ``[<pct>%]`` progress marker,
- a middot run (``···``) indentation,
- the fully-qualified benchmark name
  (``benchmarks.SampleBenchmark.time_benchmark1``), and
- a value of the form ``<mean>±<err><unit>``.

Two things make this format awkward, both handled here:

1. **The unit auto-scales** (ns / μs / ms / s) per benchmark, so a raw
   value is meaningless without its unit. We normalise every value to
   **seconds** for a stable, comparable metric. (asv's results JSON is
   always in seconds, so seconds keeps the two parsers consistent.)
2. **It's buried in a much larger CI log** (pip install chatter, asv
   machine-registration prompts, "Building"/"Installing" lines, and a
   GitHub-Actions ISO-8601 timestamp prefix on every line). We scan the
   whole content for benchmark lines and ignore everything else.

The error term (``±<err>``) is captured as an ``err`` metric in the same
unit-normalised seconds; with ``--quick`` (used in the CI run.sh) asv
takes a single sample so the error is ``0``.

The benchmark ``test_name`` is derived the same way as in the JSON
parser: take the last dotted segment of the fully-qualified name and
strip a leading ``time_`` (``benchmarks.SampleBenchmark.time_benchmark1``
→ ``benchmark1``).

See ``frameworks/language/asv/README.md``.
"""

from __future__ import annotations

import re


# Strip ANSI escape codes in case the console output was colorized.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Seconds per asv time unit. The micro sign may be U+00B5 (µ) or Greek
# mu (U+03BC); asv also occasionally emits ASCII "us".
_UNIT_S = {"ns": 1e-9, "µs": 1e-6, "μs": 1e-6, "us": 1e-6, "ms": 1e-3, "s": 1.0}
_UNIT = r"(?:ns|µs|μs|us|ms|s)"

# A benchmark result line, ignoring any leading GH-Actions timestamp and
# the "[ pct%] ··· " progress/indent chrome:
#
#   [12.50%] ··· benchmarks.SampleBenchmark.time_benchmark1   2.15±0s
#
# The value is "<mean>±<err><unit>"; "failed" / "n/a" sentinels (asv emits
# these instead of a number for errored/skipped benchmarks) are not matched
# and so are silently skipped.
_RESULT_RE = re.compile(
    r"\[\s*[0-9.]+%\]\s*[·.]+\s+"               # [ 12.50%] ···
    r"(?P<name>\S+)\s+"                          # fq benchmark name
    r"(?P<mean>[0-9.]+)"                         # mean
    r"(?:±(?P<err>[0-9.]+))?"                    # optional ±err
    r"\s*(?P<unit>" + _UNIT + r")\b"            # unit (greedy-safe \b)
)


def _normalize_name(fq_name: str) -> str:
    """``benchmarks.SampleBenchmark.time_benchmark1`` → ``benchmark1``."""
    tail = fq_name.rsplit(".", 1)[-1]
    if tail.startswith("time_"):
        tail = tail[5:]
    return tail


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    lines = [_ANSI_RE.sub("", ln) for ln in content.splitlines()]

    out: list[dict] = []
    for line in lines:
        m = _RESULT_RE.search(line)
        if not m:
            continue
        unit = m.group("unit")
        scale = _UNIT_S[unit]
        mean_s = float(m.group("mean")) * scale

        metrics: list[dict] = [
            {"name": "mean", "unit": "s", "value": mean_s,
             "direction": "lower_is_better"},
        ]
        if m.group("err") is not None:
            metrics.append(
                {"name": "err", "unit": "s",
                 "value": float(m.group("err")) * scale,
                 "direction": "lower_is_better"}
            )

        out.append({
            "test": {"test_name": _normalize_name(m.group("name"))},
            "run": {"passed": True},
            "env": {"framework": {"name": "asv"}},
            "metrics": metrics,
        })
    return out
