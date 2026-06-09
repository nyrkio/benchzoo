"""Parser for Jest's default-reporter console output.

``junit-jest`` runs the canonical sample benchmark as four Jest unit
tests and uploads ``output.xml`` (JUnit XML) as the artifact — that file
is parsed by :mod:`benchzoo.parsers.junit_standard`. But Jest *also*
prints a human-readable per-test summary to the console, and that block
is captured verbatim in the GitHub Actions job log::

    PASS ./sample.test.js
      ✓ benchmark1 (2151 ms)
      ✓ benchmark2 (2 ms)
      ✓ benchmark3 (3 ms)
      ✓ benchmark4 (1151 ms)

    Test Suites: 1 passed, 1 total
    Tests:       4 passed, 4 total

Each ``✓ NAME (N ms)`` line carries the per-test wall time in
milliseconds — the same signal as the XML ``time`` attribute, just at
millisecond rather than three-decimal-second precision. When no
artifact is available (only the CI log), this text parser recovers the
benchmark1..benchmark4 series from the log directly.

We normalise the millisecond value to **seconds** so the metric is
comparable with the ``junit_standard`` XML path (which emits seconds).

Notes on robustness:

* Jest marks passing tests with ``✓`` (U+2713) and failing tests with
  ``✗`` / ``×``; on no-unicode terminals it falls back to ASCII
  ``√`` / ``×`` or plain ``ok``/``failed``. We accept the common pass
  glyphs and mark ``passed`` accordingly; failing lines are still
  emitted (library boundary: never silently drop a result).
* Jest reports times as integer ms for fast tests and ``N.M s`` /
  ``N.M min`` for slow ones; we handle the unit suffix generically.
* Each line in a GitHub Actions *log* carries an ISO-8601 timestamp
  prefix; clean local output does not. Both are tolerated.
* Jest colorises output; ANSI escapes are stripped.
"""

from __future__ import annotations

import re


# Strip ANSI escape codes (Jest colorises its reporter output).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Optional GitHub-Actions per-line ISO-8601 timestamp prefix.
_TS = r"(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+)?"

# Jest duration unit -> seconds. Jest prints "ms" for fast tests and
# "s" / "min" for slow ones.
_UNIT_S = {"ms": 1e-3, "s": 1.0, "sec": 1.0, "min": 60.0}
_UNIT = r"(?:ms|sec|s|min)"

# Per-test result line:
#   "  ✓ benchmark1 (2151 ms)"     (pass)
#   "  ✗ benchmark1 (5 ms)"        (fail)
# The status glyph is captured so failing tests set passed=False. The
# trailing "(N unit)" is optional in Jest only for skipped tests, which
# carry a "○" glyph and no time — those we skip (no number to record).
_PASS_GLYPHS = "✓√"
_FAIL_GLYPHS = "✗×✕"
_LINE_RE = re.compile(
    r"^\s*" + _TS
    + r"(?P<glyph>[" + _PASS_GLYPHS + _FAIL_GLYPHS + r"])\s+"
    r"(?P<name>.+?)\s+"
    r"\((?P<value>[0-9]+(?:\.[0-9]+)?)\s*(?P<unit>" + _UNIT + r")\)\s*$"
)


def parse(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    out: list[dict] = []
    for raw in content.splitlines():
        m = _LINE_RE.match(_ANSI_RE.sub("", raw))
        if not m:
            continue
        name = m.group("name").strip()
        if not name:
            continue
        passed = m.group("glyph") in _PASS_GLYPHS
        seconds = float(m.group("value")) * _UNIT_S[m.group("unit")]
        out.append({
            "test": {"test_name": name},
            "run": {"passed": passed},
            "env": {"framework": {"name": "junit-jest"}},
            "metrics": [
                {"name": "duration", "unit": "s", "value": seconds,
                 "direction": "lower_is_better"},
            ],
        })
    return out
