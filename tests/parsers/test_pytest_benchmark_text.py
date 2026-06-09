"""Ground-truth tests for the pytest-benchmark terminal-table parser.

The fixture at ``tests/data/pytest-benchmark-output/output-text.txt`` is a
real slice of a GitHub Actions job log from a run of
``frameworks/language/pytest-benchmark`` (run 27059048249, 2026-06-06),
including the surrounding pytest/CI noise and the per-line ISO-8601
timestamp prefix the parser must tolerate.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import pytest_benchmark_text

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "pytest-benchmark-output"


@pytest.fixture(scope="module")
def results():
    return pytest_benchmark_text.parse((FIXTURES / "output-text.txt").read_bytes())


def _metric(d: dict, name: str) -> dict:
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


def _by_test(results: list[dict]) -> dict[str, dict]:
    return {d["test"]["test_name"]: d for d in results}


def test_has_four_test_runs(results):
    names = sorted(d["test"]["test_name"] for d in results)
    assert names == ["benchmark1", "benchmark2", "benchmark3", "benchmark4"]


def test_all_passed(results):
    for d in results:
        assert d["run"]["passed"] is True


def test_framework_name(results):
    for d in results:
        assert d["env"]["framework"]["name"] == "pytest-benchmark"


def test_benchmark1_mean_around_215s(results):
    # "Name (time in s)" table — value 2.1501.
    mean = _metric(_by_test(results)["benchmark1"], "mean")
    assert 2.0 < mean["value"] < 2.3
    assert mean["unit"] == "s"
    assert mean["direction"] == "lower_is_better"


def test_benchmark2_sub_millisecond(results):
    # "Name (time in us)" table — value 15.7732 us == ~1.6e-5 s.
    mean = _metric(_by_test(results)["benchmark2"], "mean")
    assert 0 < mean["value"] < 1e-3
    assert mean["unit"] == "s"


def test_benchmark3_small_write(results):
    # "Name (time in us)" table — value 3,205.9376 us == ~3.2e-3 s.
    # Exercises the thousands-separator stripping.
    mean = _metric(_by_test(results)["benchmark3"], "mean")
    assert 1e-3 < mean["value"] < 0.05
    assert mean["unit"] == "s"


def test_benchmark4_change_point_in_range(results):
    # June 2026 -> 1.15 s. Loose check per the spec: one of {1.15,2.15,3.15}.
    mean = _metric(_by_test(results)["benchmark4"], "mean")
    assert any(abs(mean["value"] - v) < 0.1 for v in (1.15, 2.15, 3.15))
    # The captured fixture is from June (UTC month 6 -> 1.15 s).
    assert 1.0 < mean["value"] < 1.3


def test_other_timing_metrics_present(results):
    r = _by_test(results)["benchmark1"]
    for name in ("min", "max", "stddev", "median"):
        m = _metric(r, name)
        assert m["unit"] == "s"
        assert m["direction"] == "lower_is_better"
        assert m["value"] >= 0
    # min/max/median bracket the mean for the sleep benchmark.
    assert 2.0 < _metric(r, "min")["value"] < 2.3
    assert 2.0 < _metric(r, "max")["value"] < 2.3


def test_ops_higher_is_better(results):
    # benchmark1 OPS == 1/mean ~= 0.4651.
    ops = _metric(_by_test(results)["benchmark1"], "ops")
    assert ops["unit"] == "ops/s"
    assert ops["direction"] == "higher_is_better"
    assert 0.43 < ops["value"] < 0.50
