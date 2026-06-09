"""Ground-truth tests for the mitata console-table (text) parser.

The fixture ``tests/data/mitata-output/output-text.txt`` is a real slice
of mitata's default human-readable table captured from the benchzoo CI
artifact for run 26905044903 (2026-06-03, June). Every line carries a
GitHub Actions ISO-8601 timestamp prefix, proving the parser tolerates
it; surrounding npm/CI noise is kept so the parser proves it can find
the table.

Ground truth (canonical sample benchmark, June ⇒ benchmark4 = 1.15 s):
  benchmark1 ≈ 2.15 s   benchmark2 ≈ 467.73 ns   benchmark3 ≈ 374.70 µs
  benchmark4 ≈ 1.15 s
"""

from __future__ import annotations

import pathlib

from benchzoo.parsers import mitata_text


_FIXTURE = (
    pathlib.Path(__file__).parent.parent
    / "data" / "mitata-output" / "output-text.txt"
)


def _load():
    rows = mitata_text.parse(_FIXTURE.read_bytes())
    return {r["test"]["test_name"]: r for r in rows}


def _avg_ns(row):
    return next(m["value"] for m in row["metrics"] if m["name"] == "time")


def test_all_four_benchmarks_present():
    rows = _load()
    assert set(rows) == {"benchmark1", "benchmark2", "benchmark3", "benchmark4"}


def test_framework_unit_direction():
    rows = _load()
    for row in rows.values():
        assert row["env"]["framework"]["name"] == "mitata"
        assert row["run"]["passed"] is True
        time_metric = next(m for m in row["metrics"] if m["name"] == "time")
        assert time_metric["unit"] == "ns"
        assert time_metric["direction"] == "lower_is_better"


def test_benchmark1_sleep_2_15s():
    # ~2.15 s, normalised to ns.
    v = _avg_ns(_load()["benchmark1"])
    assert 2.0e9 < v < 2.3e9


def test_benchmark2_sub_millisecond():
    # Tight CPU loop — sub-microsecond, must NOT round to zero.
    v = _avg_ns(_load()["benchmark2"])
    assert 0 < v < 1e6  # under a millisecond
    assert 100 < v < 1000  # the headline 467.73 ns


def test_benchmark3_small_write():
    # ~374.70 µs — present and non-zero, sub-second.
    v = _avg_ns(_load()["benchmark3"])
    assert 0 < v < 1e9
    assert 1e5 < v < 1e6  # hundreds of microseconds


def test_benchmark4_change_point_june_1_15s():
    # June ⇒ 2.15 + ((6 mod 3) - 1) = 1.15 s; loose membership check.
    v = _avg_ns(_load()["benchmark4"]) / 1e9  # back to seconds
    assert any(abs(v - t) < 0.1 for t in (1.15, 2.15, 3.15))
    assert abs(v - 1.15) < 0.1  # the captured June run specifically


def test_min_max_extras_present():
    row = _load()["benchmark1"]
    names = {m["name"] for m in row["metrics"]}
    assert {"time", "min", "max"} <= names
    mn = next(m["value"] for m in row["metrics"] if m["name"] == "min")
    mx = next(m["value"] for m in row["metrics"] if m["name"] == "max")
    assert mn > 0 and mx > 0 and mn <= mx
