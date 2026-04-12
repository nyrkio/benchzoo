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


def _by_test(results: list[dict]) -> dict[str, dict]:
    return {d["attributes"]["test_name"]: d for d in results}


@pytest.mark.parametrize("results", ["estimates_results", "bencher_results"])
def test_has_four_runs_named_benchmark1_through_4(results, request):
    r = request.getfixturevalue(results)
    assert len(r) == 4
    assert sorted(d["attributes"]["test_name"] for d in r) == [
        "benchmark1", "benchmark2", "benchmark3", "benchmark4"
    ]


@pytest.mark.parametrize("results", ["estimates_results", "bencher_results"])
def test_timestamp_is_zero(results, request):
    for d in request.getfixturevalue(results):
        assert d["timestamp"] == 0


@pytest.mark.parametrize("results", ["estimates_results", "bencher_results"])
def test_git_attributes_absent(results, request):
    for d in request.getfixturevalue(results):
        for key in ("git_repo", "branch", "git_commit"):
            assert key not in d["attributes"]


def test_estimates_benchmark1_mean_is_2_15_seconds(estimates_results):
    r = _by_test(estimates_results)
    mean = _metric(r["benchmark1"], "mean")
    assert 2.0e9 <= mean["value"] <= 2.3e9, mean
    assert mean["unit"] == "ns"
    assert mean["direction"] == "lower_is_better"


def test_bencher_benchmark1_ns_per_iter_is_2_15_seconds(bencher_results):
    r = _by_test(bencher_results)
    nsi = _metric(r["benchmark1"], "ns_per_iter")
    assert 2.0e9 <= nsi["value"] <= 2.3e9, nsi


@pytest.mark.parametrize("results", ["estimates_results", "bencher_results"])
def test_benchmark4_in_sleep_range(results, request):
    r = _by_test(request.getfixturevalue(results))
    # Different metric name in each parser; check any duration metric.
    metric_name = "mean" if "mean" in {m["name"] for m in r["benchmark4"]["metrics"]} else "ns_per_iter"
    duration = _metric(r["benchmark4"], metric_name)
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
    assert result[0]["attributes"]["test_name"] == "<unknown>"
