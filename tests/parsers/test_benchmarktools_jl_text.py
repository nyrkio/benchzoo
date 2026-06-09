"""Ground-truth tests for the BenchmarkTools.jl stdout (text) parser.

The fixture is a real slice of the framework's own CI job log (run
26929573347, June 2026). Expected numbers come from the canonical sample
benchmark (``docs/sample-benchmark.md``): benchmark1 ≈ 2.15 s,
benchmark2 sub-millisecond, benchmark3 a small I/O write, benchmark4 a
month-stepped sleep cycling {1.15, 2.15, 3.15} s (June → 1.15 s).
"""

from __future__ import annotations

import pathlib

from benchzoo.parsers import benchmarktools_jl_text

FIXTURE = (
    pathlib.Path(__file__).resolve().parents[1]
    / "data" / "benchmarktools-jl-output" / "output-text.txt"
)


def _by_name(rows):
    return {r["test"]["test_name"]: r for r in rows}


def test_parses_all_four_benchmarks():
    rows = benchmarktools_jl_text.parse(FIXTURE.read_bytes())
    by = _by_name(rows)
    assert set(by) == {"benchmark1", "benchmark2", "benchmark3", "benchmark4"}


def test_metric_shape_unit_direction_framework():
    rows = benchmarktools_jl_text.parse(FIXTURE.read_bytes())
    for r in rows:
        assert r["run"]["passed"] is True
        assert r["env"]["framework"]["name"] == "benchmarktools-jl"
        assert len(r["metrics"]) == 1
        m = r["metrics"][0]
        assert m["name"] == "time"
        assert m["unit"] == "s"
        assert m["direction"] == "lower_is_better"
        assert m["value"] > 0.0


def test_ground_truth_values():
    by = _by_name(benchmarktools_jl_text.parse(FIXTURE.read_bytes()))

    def v(name):
        return by[name]["metrics"][0]["value"]

    # benchmark1: ~2.15 s sleep.
    assert 2.0 < v("benchmark1") < 2.3
    # benchmark2: sub-millisecond CPU loop (nanoseconds → tiny but non-zero).
    assert 0.0 < v("benchmark2") < 1e-3
    # benchmark3: small 1.4 MB write, microseconds → non-zero, sub-ms.
    assert 0.0 < v("benchmark3") < 1e-3
    # benchmark4: month-stepped sleep, one of {1.15, 2.15, 3.15} s.
    assert any(abs(v("benchmark4") - x) < 0.1 for x in (1.15, 2.15, 3.15))


def test_tolerates_ascii_us_and_micro_sign():
    text = (
        "2026-06-04T03:57:17.0Z benchmarkA: Trial(12.5 us)\n"
        "2026-06-04T03:57:17.0Z benchmarkB: Trial(7.0 µs)\n"
    )
    by = _by_name(benchmarktools_jl_text.parse(text))
    assert abs(by["benchmarkA"]["metrics"][0]["value"] - 12.5e-6) < 1e-12
    assert abs(by["benchmarkB"]["metrics"][0]["value"] - 7.0e-6) < 1e-12
