"""Ground-truth tests for the junit-go *text* parser.

The junit-go framework wraps the canonical sample benchmark
(``docs/sample-benchmark.md``) in ``gotestsum --format=standard-verbose``,
which tees Go's own ``go test -v`` log to stdout::

    === RUN   TestBenchmark1
    --- PASS: TestBenchmark1 (2.15s)
    ...
    --- PASS: TestBenchmark4 (1.15s)

When no XML artifact is uploaded, that stdout (here read from the GitHub
Actions job *log*, ISO-8601-timestamp-prefixed) is the only signal. The
fixture ``tests/data/junit-go-output/output-text.txt`` is a real slice of
the CI run-27184022689 log (2026-06-09, June → benchmark4 = 1.15s).

Ground truth: benchmark1 ~2.15 s, benchmark4 ~1.15 s; all four present.
benchmark2/benchmark3 are sub-millisecond, which Go's two-decimal verbose
format truncates to 0.00 s — the honest value this stdout can express.
"""

from __future__ import annotations

import pathlib

from benchzoo.parsers import junit_go_text

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "junit-go-output"


def _by_name(rows):
    return {r["test"]["test_name"]: r for r in rows}


def _metric(row, name="duration"):
    for m in row["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"no metric {name!r} in {row}")


def test_canonical_benchmarks_ground_truth():
    rows = junit_go_text.parse((FIXTURES / "output-text.txt").read_text())
    by = _by_name(rows)

    # All four canonical benchmarks present, names stripped of "Test".
    assert {"benchmark1", "benchmark2", "benchmark3", "benchmark4"} <= set(by)

    # benchmark1: sleep ~2.15 s.
    v1 = _metric(by["benchmark1"])["value"]
    assert 2.0 <= v1 <= 2.3, v1

    # benchmark4: month-stepped sleep; June 2026 → 1.15 s (one of 1.15/2.15/3.15).
    v4 = _metric(by["benchmark4"])["value"]
    assert any(abs(v4 - x) < 0.1 for x in (1.15, 2.15, 3.15)), v4
    assert abs(v4 - 1.15) < 0.1, v4  # captured run is June

    # benchmark2/benchmark3 present (sub-ms; truncated to 0.00s by go test's
    # two-decimal verbose format — the value this stdout can express).
    assert _metric(by["benchmark2"])["value"] >= 0.0
    assert _metric(by["benchmark3"])["value"] >= 0.0


def test_metric_shape_and_framework():
    rows = junit_go_text.parse((FIXTURES / "output-text.txt").read_text())
    row = _by_name(rows)["benchmark1"]
    assert row["env"]["framework"]["name"] == "junit-go"
    assert row["run"]["passed"] is True
    m = _metric(row)
    assert m["unit"] == "s"
    assert m["direction"] == "lower_is_better"


def test_tolerates_timestamps_and_ansi():
    # GH-log ISO prefix + ANSI color around a real result line.
    log = (
        "2026-06-09T04:33:38.0Z === RUN   TestBenchmark1\n"
        "2026-06-09T04:33:40.1Z \x1b[32m--- PASS: TestBenchmark1 (2.15s)\x1b[0m\n"
    )
    rows = junit_go_text.parse(log)
    assert len(rows) == 1
    assert rows[0]["test"]["test_name"] == "benchmark1"
    assert abs(rows[0]["metrics"][0]["value"] - 2.15) < 0.01


def test_bytes_input_and_failure_status():
    log = b"--- FAIL: TestBenchmark1 (2.15s)\n"
    rows = junit_go_text.parse(log)
    assert len(rows) == 1
    assert rows[0]["run"]["passed"] is False
