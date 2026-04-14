"""Ground-truth tests for batch 3 parsers.

Covers hey, redis_benchmark_csv, locust_csv, tinybench, perf_stat_text,
vegeta_json. (clickbench parser added separately once its CI stabilizes.)
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import (
    hey,
    locust_csv,
    perf_stat_text,
    redis_benchmark_csv,
    tinybench,
    vegeta_json,
)

DATA = pathlib.Path(__file__).parent.parent / "data"


def _metric(d, name):
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


def _by_test(results):
    return {d["attributes"]["test_name"]: d for d in results}


# ---------------------------------------------------------------------------
# hey — one "homepage" test, localhost latency sub-ms
# ---------------------------------------------------------------------------

def test_hey():
    results = hey.parse((DATA / "hey-output/output.txt").read_text())
    assert len(results) == 1
    d = results[0]
    assert d["test"]["test_name"] == "homepage"
    assert d["env"]["framework"]["name"] == "hey"
    avg = _metric(d, "latency_avg")
    # Localhost avg is well under 100 ms
    assert avg["unit"] == "ms"
    assert 0 < avg["value"] < 100
    names = {m["name"] for m in d["metrics"]}
    assert "latency_p50" in names
    assert "latency_p99" in names
    rps = _metric(d, "requests_per_sec")
    assert rps["direction"] == "higher_is_better"
    assert rps["value"] > 100
    assert d["run"]["passed"] is True


# ---------------------------------------------------------------------------
# redis-benchmark CSV
# ---------------------------------------------------------------------------

def test_redis_benchmark_csv():
    results = redis_benchmark_csv.parse((DATA / "redis-benchmark-output/output.csv").read_text())
    # We ran SET, GET, INCR, LPUSH, RPUSH, MSET
    assert len(results) >= 5
    names = {d["test"]["test_name"] for d in results}
    assert "SET" in names
    assert "GET" in names
    by_test = {d["test"]["test_name"]: d for d in results}
    rps = _metric(by_test["SET"], "rps")
    assert rps["unit"] == "ops/s"
    assert rps["direction"] == "higher_is_better"
    assert rps["value"] > 1000  # Redis does way more than 1k rps on localhost
    p50 = _metric(by_test["SET"], "p50_latency")
    assert p50["unit"] == "ms"
    assert p50["direction"] == "lower_is_better"
    for d in results:
        assert d["env"]["framework"]["name"] == "redis-benchmark"
        assert d["run"]["passed"] is True


# ---------------------------------------------------------------------------
# Locust CSV — skips Aggregated row
# ---------------------------------------------------------------------------

def test_locust_csv():
    results = locust_csv.parse((DATA / "locust-output/output_stats.csv").read_text())
    # Sample had one real request (GET /) + Aggregated; aggregated should be skipped.
    assert len(results) == 1
    d = results[0]
    assert d["attributes"]["test_name"] == "GET /"
    names = {m["name"] for m in d["metrics"]}
    assert "latency_p50" in names
    assert "latency_p99" in names
    assert "requests_per_sec" in names
    rps = _metric(d, "requests_per_sec")
    assert rps["value"] > 0
    assert d["extra_info"]["request_count"] > 0
    assert d["passed"] is True
    assert d["timestamp"] == 0


# ---------------------------------------------------------------------------
# tinybench — latency nested, mean in milliseconds
# ---------------------------------------------------------------------------

def test_tinybench():
    results = tinybench.parse((DATA / "tinybench-output/output.json").read_text())
    assert len(results) == 4
    by_test = _by_test(results)
    mean = _metric(by_test["benchmark1"], "mean")
    # Milliseconds
    assert 2000 <= mean["value"] <= 2300, mean
    assert mean["unit"] == "ms"
    hz = _metric(by_test["benchmark1"], "hz")
    assert hz["direction"] == "higher_is_better"
    for d in results:
        assert d["timestamp"] == 0


# ---------------------------------------------------------------------------
# vegeta JSON — single "homepage" test, latencies in ns normalized to ms
# ---------------------------------------------------------------------------

def test_vegeta_json():
    results = vegeta_json.parse((DATA / "vegeta-output/output.json").read_text())
    assert len(results) == 1
    d = results[0]
    assert d["attributes"]["test_name"] == "homepage"
    mean = _metric(d, "latency_mean")
    assert mean["unit"] == "ms"
    # Localhost attack — well under 100 ms mean latency
    assert 0 < mean["value"] < 100
    rate = _metric(d, "rate")
    assert rate["direction"] == "higher_is_better"
    assert rate["value"] > 50  # we attacked at ~100 req/s
    success = _metric(d, "success_ratio")
    assert success["value"] == 1
    assert d["extra_info"]["requests"] > 0
    assert d["passed"] is True
    assert d["timestamp"] == 0


# ---------------------------------------------------------------------------
# perf stat text — wall_time from "seconds time elapsed" line
# ---------------------------------------------------------------------------

def test_perf_stat_text():
    results = perf_stat_text.parse((DATA / "perf-stat-output/output-text.txt").read_text())
    assert {d["test"]["test_name"] for d in results} == {
        "benchmark1", "benchmark2", "benchmark3", "benchmark4"
    }
    by_test = {d["test"]["test_name"]: d for d in results}
    wall = _metric(by_test["benchmark1"], "wall_time")
    # benchmark1 sleeps 2.15 s; perf reports "seconds time elapsed"
    assert 2.0 <= wall["value"] <= 2.3, wall
    assert wall["unit"] == "s"
    # page-faults should have non-zero count (even if <cycles> is not supported)
    pf = _metric(by_test["benchmark1"], "page_faults")
    assert pf["value"] > 0
    for d in results:
        assert d["env"]["framework"]["name"] == "perf-stat"
        assert d["run"]["passed"] is True
