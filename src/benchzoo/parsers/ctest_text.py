"""Parser for CTest's human-readable console output.

CTest (CMake's test runner) prints, per registered test, a one-line
result to stdout as it runs::

    Test project /path/to/build
        Start 1: benchmark1
    1/4 Test #1: benchmark1 .......................   Passed    2.15 sec
        Start 2: benchmark2
    2/4 Test #2: benchmark2 .......................   Passed    0.00 sec
    ...
    100% tests passed, 0 tests failed out of 4

    Total Test time (real) =   3.39 sec

The ``--output-junit`` artifact (parsed by ``junit_standard``) is the
preferred, higher-precision source — its ``time`` attribute carries full
float precision (e.g. ``2.15403``). But when a CI job only prints CTest's
console output to the log and uploads no artifact, this parser recovers
the per-test wall times from the ``N/M Test #K: NAME ... Passed/Failed
T sec`` result lines instead.

Caveats vs. the junit artifact:

- **Precision** — the console line rounds the duration to two decimals
  (``2.15 sec``, ``1.16 sec``), where the junit ``time`` keeps the full
  float. Sub-10ms tests collapse to ``0.00`` / ``0.01``.
- **Pass/fail** — ``Passed`` -> ``passed: True``; anything else
  (``Failed``, ``Timeout``, ``Exception``, etc.) -> ``passed: False``.

These result lines are usually buried in a larger CI log (CMake configure
output, ``Start N:`` lines, the summary footer), and when read from a
GitHub Actions job log every line carries an ISO-8601 timestamp prefix —
so we scan the whole content for the result lines and tolerate the prefix
and ANSI colour codes.
"""

from __future__ import annotations

import re


# Strip ANSI escapes (CTest colourises Passed/Failed in a TTY, and CI
# logs sometimes preserve the codes).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Optional GitHub-Actions per-line ISO-8601 timestamp prefix. Present when
# the output is read from a job *log* (no artifact uploaded); absent in a
# clean capture. Tolerate either.
_TS = r"(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?"

# CTest's per-test result line:
#   "1/4 Test #1: benchmark1 .......................   Passed    2.15 sec"
# - "N/M" is the completed/total counter.
# - "Test #K:" is the test ordinal.
# - the name runs up to the run of dots CTest pads with.
# - the status word ("Passed", "Failed", "Timeout", "Exception", ...).
# - the duration in seconds (always "sec" in CTest's default output).
_RESULT_RE = re.compile(
    r"^\s*" + _TS
    + r"\d+/\d+\s+Test\s+#\d+:\s+"
    r"(?P<name>\S.*?)\s+\.{2,}\s*"
    r"(?P<status>\*{3}\s*)?(?P<word>\w[\w ]*?)\s+"
    r"(?P<value>[0-9]+(?:\.[0-9]+)?)\s+sec\b"
)


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    out: list[dict] = []
    for raw in content.splitlines():
        m = _RESULT_RE.match(_ANSI_RE.sub("", raw))
        if not m:
            continue
        name = m.group("name").strip()
        if not name:
            continue
        passed = m.group("word").strip() == "Passed"
        seconds = float(m.group("value"))
        out.append({
            "test": {"test_name": name},
            "run": {"passed": passed},
            "env": {"framework": {"name": "ctest"}},
            "metrics": [
                {"name": "time", "unit": "s", "value": seconds,
                 "direction": "lower_is_better"},
            ],
        })
    return out
