"""Ground-truth tests for the PHPBench console (aggregate) text parser.

Fixture is a real slice of the phpbench CI job log (run 27171453692,
captured 2026-06-08 = June), so every line carries the GitHub Actions
ISO-8601 timestamp prefix. benchmark4's June value is 1.15 s.
"""

from __future__ import annotations

from pathlib import Path

from benchzoo.parsers.phpbench_text import parse


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "data" / "phpbench-output" / "output-text.txt"
)


def _by_name(results: list[dict]) -> dict[str, dict]:
    return {r["test"]["test_name"]: r for r in results}


def _mode(result: dict) -> dict:
    return next(m for m in result["metrics"] if m["name"] == "mode")


def test_parses_four_benchmarks():
    results = parse(FIXTURE.read_text())
    names = {r["test"]["test_name"] for r in results}
    assert names == {"benchmark1", "benchmark2", "benchmark3", "benchmark4"}


def test_benchmark1_wall_time():
    results = _by_name(parse(FIXTURE.read_text()))
    mode = _mode(results["benchmark1"])
    assert 2.0 < mode["value"] < 2.3            # known sleep is 2.15 s
    assert mode["unit"] == "s"
    assert mode["direction"] == "lower_is_better"


def test_benchmark2_sub_millisecond():
    results = _by_name(parse(FIXTURE.read_text()))
    mode = _mode(results["benchmark2"])
    # Tight CPU loop, ~microseconds; must be non-zero and well under 1 ms.
    assert 0.0 < mode["value"] < 1e-3
    assert mode["unit"] == "s"


def test_benchmark3_small_write():
    results = _by_name(parse(FIXTURE.read_text()))
    mode = _mode(results["benchmark3"])
    # 1.4 MB write, a few ms; non-zero and sub-second.
    assert 0.0 < mode["value"] < 0.1
    assert mode["unit"] == "s"


def test_benchmark4_monthly_change_point():
    results = _by_name(parse(FIXTURE.read_text()))
    mode = _mode(results["benchmark4"])
    # June -> 1.15 s; loose check against the cycle {1.15, 2.15, 3.15}.
    assert any(abs(mode["value"] - v) < 0.1 for v in (1.15, 2.15, 3.15))
    assert abs(mode["value"] - 1.15) < 0.1
    assert mode["unit"] == "s"


def test_framework_name_and_passed():
    for r in parse(FIXTURE.read_text()):
        assert r["env"]["framework"]["name"] == "phpbench"
        assert r["run"]["passed"] is True


def test_extra_info_revs_iterations():
    results = _by_name(parse(FIXTURE.read_text()))
    assert results["benchmark2"]["extra_info"]["revs"] == 1000
    assert results["benchmark1"]["extra_info"]["iterations"] == 3
