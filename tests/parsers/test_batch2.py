"""Ground-truth tests for batch 2 parsers.

One file covering cargo_bench_libtest, benchmark_js, vitest_bench,
wrk, junit_standard (jest + vanilla fixtures), junit_go, catch2_xml. All fixtures
come from real GitHub Actions runs; all parsers verify that
benchmark1 represents ~2.15 s of work.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import (
    asv,
    benchmark_js,
    cargo_bench_libtest,
    catch2_xml,
    junit_go,
    junit_standard,
    vitest_bench,
    wrk,
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
# cargo bench (libtest) — delegates to criterion_bencher
# ---------------------------------------------------------------------------

def test_cargo_bench_libtest():
    results = cargo_bench_libtest.parse((DATA / "cargo-bench-output/output.txt").read_text())
    assert {d["test"]["test_name"] for d in results} == {
        "benchmark1", "benchmark2", "benchmark3", "benchmark4"
    }
    by_test = {d["test"]["test_name"]: d for d in results}
    nsi = _metric(by_test["benchmark1"], "ns_per_iter")
    assert 2.0e9 <= nsi["value"] <= 2.3e9, nsi
    assert nsi["unit"] == "ns"
    for d in results:
        assert d["env"]["framework"]["name"] == "cargo-bench"
        assert d["run"]["passed"] is True


# ---------------------------------------------------------------------------
# benchmark.js — mean in SECONDS
# ---------------------------------------------------------------------------

def test_benchmark_js():
    results = benchmark_js.parse((DATA / "benchmark-js-output/output.json").read_text())
    assert len(results) == 4
    by_test = {d["test"]["test_name"]: d for d in results}
    mean = _metric(by_test["benchmark1"], "mean")
    # Mean is SECONDS per op (benchmark.js native unit)
    assert 2.0 <= mean["value"] <= 2.3, mean
    assert mean["unit"] == "s"
    hz = _metric(by_test["benchmark1"], "hz")
    assert hz["unit"] == "ops/s"
    assert hz["direction"] == "higher_is_better"
    # samples ends up in extra_info
    assert by_test["benchmark1"]["extra_info"]["samples"] > 0
    for d in results:
        assert d["env"]["framework"]["name"] == "benchmark-js"
        assert d["run"]["passed"] is True


# ---------------------------------------------------------------------------
# vitest-bench — mean in MILLISECONDS
# ---------------------------------------------------------------------------

def test_vitest_bench():
    results = vitest_bench.parse((DATA / "vitest-bench-output/output.json").read_text())
    assert len(results) == 4
    by_test = {d["test"]["test_name"]: d for d in results}
    mean = _metric(by_test["benchmark1"], "mean")
    # tinybench reports milliseconds
    assert 2000 <= mean["value"] <= 2300, mean
    assert mean["unit"] == "ms"
    # describe() block ends up in test.group
    assert by_test["benchmark1"]["test"].get("group")
    for d in results:
        assert d["env"]["framework"]["name"] == "vitest-bench"
        assert d["run"]["passed"] is True


# ---------------------------------------------------------------------------
# wrk — single "homepage" test with latency distribution
# ---------------------------------------------------------------------------

def test_wrk():
    results = wrk.parse((DATA / "wrk-output/output.txt").read_text())
    assert len(results) == 1
    d = results[0]
    assert d["test"]["test_name"] == "homepage"
    assert d["env"]["framework"]["name"] == "wrk"
    # latency_avg should be well below 100 ms for localhost static content
    avg = _metric(d, "latency_avg")
    assert avg["unit"] == "ms"
    assert 0 < avg["value"] < 100, avg
    # latency percentiles present
    names = {m["name"] for m in d["metrics"]}
    assert "latency_p50" in names
    assert "latency_p99" in names
    # throughput
    rps = _metric(d, "requests_per_sec")
    assert rps["unit"] == "ops/s"
    assert rps["direction"] == "higher_is_better"
    assert rps["value"] > 100
    assert d["run"]["passed"] is True


# ---------------------------------------------------------------------------
# junit_standard against the jest-junit fixture — 4 tests with time attribute
# ---------------------------------------------------------------------------

def test_junit_standard_jest():
    results = junit_standard.parse((DATA / "junit-jest-output/output.xml").read_text())
    assert {d["test"]["test_name"] for d in results} == {
        "benchmark1", "benchmark2", "benchmark3", "benchmark4"
    }
    by_test = {d["test"]["test_name"]: d for d in results}
    duration = _metric(by_test["benchmark1"], "duration")
    assert 2.0 <= duration["value"] <= 2.3, duration
    assert duration["unit"] == "s"
    for d in results:
        assert d["env"]["framework"]["name"] == "junit-standard"
        assert d["run"]["passed"] is True


# ---------------------------------------------------------------------------
# junit_go — TestBenchmarkN → benchmarkN normalization
# ---------------------------------------------------------------------------

def test_junit_go():
    results = junit_go.parse((DATA / "junit-go-output/output.xml").read_text())
    names = {d["test"]["test_name"] for d in results}
    # Expect our 4 tests after stripping "Test" prefix
    assert "benchmark1" in names
    assert "benchmark4" in names
    by_test = {d["test"]["test_name"]: d for d in results}
    duration = _metric(by_test["benchmark1"], "duration")
    assert 2.0 <= duration["value"] <= 2.3, duration
    assert duration["unit"] == "s"
    for d in results:
        assert d["env"]["framework"]["name"] == "junit-go"


# ---------------------------------------------------------------------------
# junit_standard against the Maven Surefire fixture — no name transformation
# ---------------------------------------------------------------------------

def test_junit_standard_vanilla():
    results = junit_standard.parse((DATA / "junit-vanilla-output/output.xml").read_text())
    names = {d["test"]["test_name"] for d in results}
    # Vanilla preserves names verbatim — benchmark1 etc.
    assert "benchmark1" in names
    by_test = {d["test"]["test_name"]: d for d in results}
    duration = _metric(by_test["benchmark1"], "duration")
    assert 2.0 <= duration["value"] <= 2.3, duration
    assert duration["unit"] == "s"
    # classname → test.group: Surefire uses the fully-qualified class
    assert "SampleTest" in by_test["benchmark1"]["test"]["group"]
    for d in results:
        assert d["env"]["framework"]["name"] == "junit-standard"


# ---------------------------------------------------------------------------
# asv — positional-column JSON schema
# ---------------------------------------------------------------------------

def test_asv():
    results = asv.parse((DATA / "asv-output/output.json").read_text())
    assert {d["attributes"]["test_name"] for d in results} == {
        "benchmark1", "benchmark2", "benchmark3", "benchmark4"
    }
    by_test = _by_test(results)
    mean = _metric(by_test["benchmark1"], "mean")
    # asv reports mean in seconds
    assert 2.0 <= mean["value"] <= 2.3, mean
    assert mean["unit"] == "s"
    for d in results:
        assert d["timestamp"] == 0
        assert "git_commit" not in d["attributes"]


# ---------------------------------------------------------------------------
# catch2_xml — native XML reporter
# ---------------------------------------------------------------------------

def test_catch2_xml():
    results = catch2_xml.parse((DATA / "catch2-output/output.xml").read_text())
    assert len(results) == 4
    by_test = _by_test(results)
    mean = _metric(by_test["benchmark1"], "mean")
    # Catch2 XML reports nanoseconds
    assert 2.0e9 <= mean["value"] <= 2.3e9, mean
    assert mean["unit"] == "ns"
    # extra_info carries sample/iteration counts
    ei = by_test["benchmark1"]["extra_info"]
    assert ei["samples"] == 3  # --benchmark-samples=3 from run.sh
    for d in results:
        assert d["timestamp"] == 0
        assert d["passed"] is True
