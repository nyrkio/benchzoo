"""Ground-truth tests for criterion parsers.

Fixtures at ``tests/data/criterion-output/`` come from a real CI run
of ``frameworks/language/criterion``. benchmark1 and benchmark4 both
measure ~2.15 s sleeps in nanoseconds.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import criterion_bencher, criterion_estimates

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "criterion-output"


@pytest.fixture(scope="module")
def estimates_results():
    return criterion_estimates.parse_directory(FIXTURES / "output")


@pytest.fixture(scope="module")
def bencher_results():
    return criterion_bencher.parse((FIXTURES / "output-bencher.txt").read_text())


def _metric(d: dict, name: str) -> dict:
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


# ---------------------------------------------------------------------------
# criterion_bencher (v2 schema)
# ---------------------------------------------------------------------------

def _b_by_test(results):
    return {d["test"]["test_name"]: d for d in results}


def test_bencher_has_four(bencher_results):
    assert len(bencher_results) == 4
    assert sorted(d["test"]["test_name"] for d in bencher_results) == [
        "benchmark1", "benchmark2", "benchmark3", "benchmark4"
    ]


def test_bencher_framework_name(bencher_results):
    for d in bencher_results:
        assert d["env"]["framework"]["name"] == "criterion"


def test_bencher_benchmark1_ns_per_iter_is_2_15_seconds(bencher_results):
    r = _b_by_test(bencher_results)
    nsi = _metric(r["benchmark1"], "ns_per_iter")
    assert 2.0e9 <= nsi["value"] <= 2.3e9, nsi


def test_bencher_benchmark4_in_sleep_range(bencher_results):
    r = _b_by_test(bencher_results)
    duration = _metric(r["benchmark4"], "ns_per_iter")
    assert 1.0e9 <= duration["value"] <= 3.3e9, duration


# ---------------------------------------------------------------------------
# criterion_estimates (v2 schema)
# ---------------------------------------------------------------------------

def _e_by_test(results):
    return {d["test"]["test_name"]: d for d in results}


def test_estimates_has_four(estimates_results):
    assert len(estimates_results) == 4
    assert sorted(d["test"]["test_name"] for d in estimates_results) == [
        "benchmark1", "benchmark2", "benchmark3", "benchmark4"
    ]


def test_estimates_framework_name(estimates_results):
    for d in estimates_results:
        assert d["env"]["framework"]["name"] == "criterion"


def test_estimates_benchmark1_mean_is_2_15_seconds(estimates_results):
    r = _e_by_test(estimates_results)
    mean = _metric(r["benchmark1"], "mean")
    assert 2.0e9 <= mean["value"] <= 2.3e9, mean
    assert mean["unit"] == "ns"
    assert mean["direction"] == "lower_is_better"


def test_estimates_benchmark4_in_sleep_range(estimates_results):
    r = _e_by_test(estimates_results)
    duration = _metric(r["benchmark4"], "mean")
    assert 1.0e9 <= duration["value"] <= 3.3e9, duration


def test_estimates_emits_median_and_stddev(estimates_results):
    """The estimates.json parser exposes more stats than bencher text."""
    for d in estimates_results:
        names = {m["name"] for m in d["metrics"]}
        assert "mean" in names
        assert "median" in names
        assert "std_dev" in names


# parse() without a known filename stubs test_name as "<unknown>"
def test_parse_without_filename_yields_unknown_test_name():
    sample = '{"mean":{"point_estimate":1000,"standard_error":1,"confidence_interval":{"confidence_level":0.95,"lower_bound":1,"upper_bound":1}}}'
    result = criterion_estimates.parse(sample)
    assert result[0]["test"]["test_name"] == "<unknown>"
