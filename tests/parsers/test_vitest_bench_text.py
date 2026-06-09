"""Ground-truth tests for the vitest-bench default-reporter text parser.

Fixture is a real slice of a GitHub-Actions job log
(``tests/data/vitest-bench-output/output-text.txt``): ANSI-colorized,
ISO-8601 timestamp prefixes, npm-install noise, the experimental-feature
banner, and a trailing ``BENCH Summary`` section around the table.
"""

from __future__ import annotations

from pathlib import Path

from benchzoo.parsers.vitest_bench_text import parse

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "data" / "vitest-bench-output" / "output-text.txt"
)


def _by_name(results):
    return {r["test"]["test_name"]: r for r in results}


def test_parses_all_four_benchmarks():
    results = parse(FIXTURE.read_bytes())
    names = {r["test"]["test_name"] for r in results}
    assert names == {"benchmark1", "benchmark2", "benchmark3", "benchmark4"}


def test_framework_name_and_passed():
    for r in parse(FIXTURE.read_text()):
        assert r["env"]["framework"]["name"] == "vitest-bench"
        assert r["run"]["passed"] is True


def test_benchmark1_wall_time():
    r = _by_name(parse(FIXTURE.read_text()))["benchmark1"]
    mean = next(m for m in r["metrics"] if m["name"] == "mean")
    # 2.15 s sleep, tinybench reports ms -> ~2150 ms.
    assert 2100.0 < mean["value"] < 2200.0
    assert mean["unit"] == "ms"
    assert mean["direction"] == "lower_is_better"


def test_benchmark4_change_detection_value():
    r = _by_name(parse(FIXTURE.read_text()))["benchmark4"]
    mean = next(m for m in r["metrics"] if m["name"] == "mean")
    seconds = mean["value"] / 1000.0
    # benchmark4 cycles {1.15, 2.15, 3.15} s; captured in June -> 1.15 s.
    assert any(abs(seconds - v) < 0.1 for v in (1.15, 2.15, 3.15))
    assert abs(seconds - 1.15) < 0.1


def test_benchmark2_sub_millisecond_not_rounded():
    r = _by_name(parse(FIXTURE.read_text()))["benchmark2"]
    mean = next(m for m in r["metrics"] if m["name"] == "mean")
    # Tight CPU loop -> sub-millisecond, must not round to zero.
    assert 0.0 < mean["value"] < 1.0


def test_benchmark3_present_and_nonzero():
    r = _by_name(parse(FIXTURE.read_text()))["benchmark3"]
    mean = next(m for m in r["metrics"] if m["name"] == "mean")
    assert mean["value"] > 0.0


def test_hz_is_higher_is_better_and_thousands_parsed():
    r = _by_name(parse(FIXTURE.read_text()))["benchmark2"]
    hz = next(m for m in r["metrics"] if m["name"] == "hz")
    assert hz["unit"] == "ops/s"
    assert hz["direction"] == "higher_is_better"
    # 124,736.49 in the log -> comma thousands separator handled.
    assert hz["value"] > 100_000.0


def test_samples_in_extra_info():
    r = _by_name(parse(FIXTURE.read_text()))["benchmark2"]
    assert r["extra_info"]["samples"] == 62369
