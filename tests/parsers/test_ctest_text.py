"""Ground-truth tests for the ctest console-output (text) parser.

CTest's preferred benchzoo source is its ``--output-junit`` artifact
(``ctest-output/output.xml``, parsed by ``junit_standard``). But when a CI
job only prints CTest's console output to the log and uploads no artifact,
``ctest_text`` recovers the per-test wall times from CTest's result lines::

    1/4 Test #1: benchmark1 .......................   Passed    2.15 sec

``tests/data/ctest-output/output-text.txt`` is a real slice of the ctest
workflow's GitHub Actions job log (run 26939365494, captured 2026-06-04),
so every line carries the ISO-8601 timestamp prefix and the parser proves
it can find the result block amid CMake-configure noise and the summary
footer.

Ground truth (docs/sample-benchmark.md): benchmark1 ~2.15 s; benchmark4 in
``{1.15, 2.15, 3.15}`` (the June capture rounds to 1.16 sec). benchmark2
and benchmark3 are bash-startup dominated and round to 0.00 / 0.01 sec in
CTest's two-decimal console output, so they are asserted present but not
non-zero.
"""

from __future__ import annotations

import pathlib

from benchzoo.parsers import ctest_text

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "ctest-output"


def _by_name(rows):
    return {r["test"]["test_name"]: r for r in rows}


def _metric(row, name="time"):
    for m in row["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"no metric {name!r} in {row}")


def test_canonical_benchmarks_ground_truth():
    rows = ctest_text.parse((FIXTURES / "output-text.txt").read_text())
    by = _by_name(rows)
    assert {"benchmark1", "benchmark2", "benchmark3", "benchmark4"} <= set(by)

    # framework name + metric shape on every row
    for row in by.values():
        assert row["env"]["framework"]["name"] == "ctest"
        assert row["run"]["passed"] is True
        m = _metric(row)
        assert m["unit"] == "s"
        assert m["direction"] == "lower_is_better"

    # benchmark1 — sleep-dominated ~2.15 s
    t1 = _metric(by["benchmark1"])["value"]
    assert 2.0 < t1 < 2.3, t1

    # benchmark4 — change-detection showcase, one of {1.15, 2.15, 3.15}
    # (CTest's console rounds to 2 decimals; June 2026 -> 1.15 -> "1.16").
    t4 = _metric(by["benchmark4"])["value"]
    assert any(abs(t4 - v) < 0.05 for v in (1.15, 2.15, 3.15)), t4

    # benchmark2 / benchmark3 — present, non-negative (round to ~0 in
    # the 2-decimal console output; the junit artifact keeps precision).
    assert _metric(by["benchmark2"])["value"] >= 0.0
    assert _metric(by["benchmark3"])["value"] >= 0.0


def test_timestamp_and_failed_status():
    # Tolerates the GH-log ISO prefix and flips passed=False on non-Passed.
    log = (
        "2026-06-04T08:09:33.9857948Z 1/4 Test #1: benchmark1 "
        "...............   Passed    2.15 sec\n"
        "2026-06-04T08:09:34.0000000Z 2/4 Test #2: benchmark2 "
        "...............***Failed    0.50 sec\n"
    )
    by = _by_name(ctest_text.parse(log))
    assert by["benchmark1"]["run"]["passed"] is True
    assert 2.0 < _metric(by["benchmark1"])["value"] < 2.3
    assert by["benchmark2"]["run"]["passed"] is False
    assert _metric(by["benchmark2"])["value"] == 0.5
