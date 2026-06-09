"""Ground-truth tests for the benchmark-ips text (console) parser.

Fixture at ``tests/data/benchmark-ips-output/output-text.txt`` is a real
slice of the benchmark-ips CI job log (GitHub Actions run 27006875047,
captured 2026-06-05 = June, UTC month 6). Each line still carries its
ISO-8601 timestamp prefix and ANSI colour codes, so the parser proves it
can find the "Calculating" table inside raw log noise.

benchmark-ips reports throughput (i/s) and a time-per-iteration; for the
sleep-dominated tests the time-per-iteration is the wall time:
benchmark1 ≈ 2.15 s/i, and benchmark4 ≈ 1.15 s/i in June.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import benchmark_ips_text

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "benchmark-ips-output"


@pytest.fixture(scope="module")
def results():
    return benchmark_ips_text.parse((FIXTURES / "output-text.txt").read_text())


@pytest.fixture(scope="module")
def by_name(results):
    return {r["test"]["test_name"]: r for r in results}


def _metric(row, name):
    return next(m for m in row["metrics"] if m["name"] == name)


def test_all_four_benchmarks_present(by_name):
    assert set(by_name) == {"benchmark1", "benchmark2", "benchmark3", "benchmark4"}


def test_framework_name(by_name):
    for row in by_name.values():
        assert row["env"]["framework"]["name"] == "benchmark-ips"
        assert row["run"]["passed"] is True


def test_benchmark1_wall_time(by_name):
    t = _metric(by_name["benchmark1"], "time_per_iteration")
    assert 2.0 < t["value"] < 2.3        # 2.15 s sleep
    assert t["unit"] == "s"
    assert t["direction"] == "lower_is_better"


def test_benchmark4_wall_time_loose(by_name):
    # benchmark4 sleeps 2.15 + ((month % 3) - 1); one of {1.15, 2.15, 3.15}.
    # Fixture captured in June -> 1.15 s.
    t = _metric(by_name["benchmark4"], "time_per_iteration")
    assert any(abs(t["value"] - v) < 0.2 for v in (1.15, 2.15, 3.15))
    assert abs(t["value"] - 1.15) < 0.2  # June-specific (stronger)
    assert t["unit"] == "s"


def test_benchmark2_and_3_present_nonzero(by_name):
    for name in ("benchmark2", "benchmark3"):
        t = _metric(by_name[name], "time_per_iteration")
        assert t["value"] > 0
        # sub-second CPU / IO tests
        assert t["value"] < 1.0
        assert t["unit"] == "s"


def test_ips_throughput_higher_is_better(by_name):
    # benchmark2 is the fastest -> highest ips.
    ips2 = _metric(by_name["benchmark2"], "ips")
    ips1 = _metric(by_name["benchmark1"], "ips")
    assert ips2["direction"] == "higher_is_better"
    assert ips2["unit"] == "iterations/second"
    assert ips2["value"] > 1000          # 23k i/s
    assert ips1["value"] < 1.0           # ~0.465 i/s for a 2.15 s sleep
    # ips and time-per-iteration are reciprocals.
    t1 = _metric(by_name["benchmark1"], "time_per_iteration")
    assert abs(ips1["value"] * t1["value"] - 1.0) < 0.05
