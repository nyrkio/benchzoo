"""Ground-truth tests for the k6 summary and ndjson parsers.

Fixtures at ``tests/data/k6-output/`` come from a real GitHub Actions
run of ``frameworks/loadtest/k6``. benchmark1 and benchmark4 measure
~2.15 s sleeps in milliseconds (k6's Trend unit for time metrics);
benchmark2 is a sub-ms loop and collapses to 0 under Date.now()'s ms
resolution; benchmark3 allocates + touches 1.4 MB of memory.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import k6_ndjson, k6_summary

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "k6-output"


@pytest.fixture(scope="module")
def summary_results():
    return k6_summary.parse((FIXTURES / "summary.json").read_text())


@pytest.fixture(scope="module")
def ndjson_results():
    return k6_ndjson.parse((FIXTURES / "output.json").read_text())


def _metric(d: dict, name: str) -> dict:
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


def _by_test(results: list[dict]) -> dict[str, dict]:
    return {d["attributes"]["test_name"]: d for d in results}


# Structural
@pytest.mark.parametrize("results", ["summary_results", "ndjson_results"])
def test_has_four_benchmark_runs(results, request):
    r = request.getfixturevalue(results)
    assert len(r) == 4
    assert [d["attributes"]["test_name"] for d in r] == [
        "benchmark1", "benchmark2", "benchmark3", "benchmark4"
    ]


@pytest.mark.parametrize("results", ["summary_results", "ndjson_results"])
def test_timestamp_is_zero(results, request):
    for d in request.getfixturevalue(results):
        assert d["timestamp"] == 0


@pytest.mark.parametrize("results", ["summary_results", "ndjson_results"])
def test_git_attributes_absent(results, request):
    for d in request.getfixturevalue(results):
        for key in ("git_repo", "branch", "git_commit"):
            assert key not in d["attributes"]


@pytest.mark.parametrize("results", ["summary_results", "ndjson_results"])
def test_only_custom_trends(results, request):
    """Parsers must skip k6's built-in metrics (vus, iterations, ...)."""
    for d in request.getfixturevalue(results):
        assert d["attributes"]["test_name"].startswith("benchmark")


# Ground truth
@pytest.mark.parametrize("results", ["summary_results", "ndjson_results"])
def test_benchmark1_avg_is_2150ms(results, request):
    r = _by_test(request.getfixturevalue(results))
    avg = _metric(r["benchmark1"], "avg")
    # k6 Trend values for time metrics are in milliseconds
    assert 2000 <= avg["value"] <= 2300, avg
    assert avg["unit"] == "ms"
    assert avg["direction"] == "lower_is_better"


@pytest.mark.parametrize("results", ["summary_results", "ndjson_results"])
def test_benchmark2_sub_10ms(results, request):
    """Empty loop + Date.now() ms resolution → typically 0 ms."""
    r = _by_test(request.getfixturevalue(results))
    avg = _metric(r["benchmark2"], "avg")
    assert 0 <= avg["value"] <= 10, avg


@pytest.mark.parametrize("results", ["summary_results", "ndjson_results"])
def test_benchmark3_sub_100ms(results, request):
    r = _by_test(request.getfixturevalue(results))
    avg = _metric(r["benchmark3"], "avg")
    assert 0 <= avg["value"] <= 100, avg


@pytest.mark.parametrize("results", ["summary_results", "ndjson_results"])
def test_benchmark4_in_range(results, request):
    r = _by_test(request.getfixturevalue(results))
    avg = _metric(r["benchmark4"], "avg")
    # 1.15 / 2.15 / 3.15 seconds depending on month → ms
    assert 1000 <= avg["value"] <= 3300, avg


@pytest.mark.parametrize("results", ["summary_results", "ndjson_results"])
def test_all_passed(results, request):
    for d in request.getfixturevalue(results):
        assert d["passed"] is True


# Summary-only: p90/p95 present
def test_summary_has_p90_p95(summary_results):
    for d in summary_results:
        names = {m["name"] for m in d["metrics"]}
        assert "p90" in names
        assert "p95" in names


# ndjson-only: extra_info records sample count (1 per metric in this corpus)
def test_ndjson_records_sample_count(ndjson_results):
    for d in ndjson_results:
        assert d["extra_info"]["samples"] == 1
