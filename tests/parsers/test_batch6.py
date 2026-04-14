"""Ground-truth tests for batch 6 parsers.

Covers mitata and benchmarktools_jl.
(phpbench, benchmark_ips added separately once their re-runs land.)
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import benchmark_ips, benchmarktools_jl, mitata, phpbench_xml

DATA = pathlib.Path(__file__).parent.parent / "data"


def _metric(d, name):
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


def _by_test(results):
    return {d["attributes"]["test_name"]: d for d in results}


def test_mitata():
    r = mitata.parse((DATA / "mitata-output/output.json").read_text())
    names = {d["test"]["test_name"] for d in r}
    assert {"benchmark1", "benchmark2", "benchmark3", "benchmark4"} <= names
    by = {d["test"]["test_name"]: d for d in r}
    mean = _metric(by["benchmark1"], "mean")
    # mitata stats are in nanoseconds
    assert 2.0e9 <= mean["value"] <= 2.3e9, mean
    assert mean["unit"] == "ns"
    # p99, p999 also exposed
    names_b1 = {m["name"] for m in by["benchmark1"]["metrics"]}
    assert "p99" in names_b1
    for d in r:
        assert d["env"]["framework"]["name"] == "mitata"
        assert d["run"]["passed"] is True


def test_benchmark_ips():
    r = benchmark_ips.parse((DATA / "benchmark-ips-output/output.json").read_text())
    names = {d["test"]["test_name"] for d in r}
    assert {"benchmark1", "benchmark2", "benchmark3", "benchmark4"} <= names
    by = {d["test"]["test_name"]: d for d in r}
    mean = _metric(by["benchmark1"], "mean")
    assert mean["unit"] == "s"
    assert mean["direction"] == "lower_is_better"
    assert 2.0 <= mean["value"] <= 2.3
    ips = _metric(by["benchmark1"], "ips")
    assert ips["unit"] == "ops/s"
    assert ips["direction"] == "higher_is_better"
    # 1/2.15 ≈ 0.465
    assert 0.4 < ips["value"] < 0.6
    # benchmark2 (empty loop) should hit very high ips
    ips2 = _metric(by["benchmark2"], "ips")
    assert ips2["value"] > 100
    for d in r:
        assert d["env"]["framework"]["name"] == "benchmark-ips"
        assert d["run"]["passed"] is True


def test_phpbench_xml():
    r = phpbench_xml.parse((DATA / "phpbench-output/output.xml").read_text())
    names = {d["test"]["test_name"] for d in r}
    assert {"benchmark1", "benchmark2", "benchmark3", "benchmark4"} <= names
    by = {d["test"]["test_name"]: d for d in r}
    mean = _metric(by["benchmark1"], "mean")
    # PHPBench XML emits microseconds; parser converts to seconds
    assert mean["unit"] == "s"
    assert 2.0 <= mean["value"] <= 2.3, mean
    assert mean["direction"] == "lower_is_better"
    for d in r:
        assert d["env"]["framework"]["name"] == "phpbench"
        assert d["run"]["passed"] is True


def test_benchmarktools_jl():
    r = benchmarktools_jl.parse(
        (DATA / "benchmarktools-jl-output/output.json").read_text()
    )
    names = {d["attributes"]["test_name"] for d in r}
    assert {"benchmark1", "benchmark2", "benchmark3", "benchmark4"} <= names
    by = _by_test(r)
    mean = _metric(by["benchmark1"], "mean")
    assert 2.0e9 <= mean["value"] <= 2.3e9, mean
    assert mean["unit"] == "ns"
    # memory / allocs show up in extra_info (BenchmarkTools emits them)
    assert "memory_bytes" in by["benchmark1"].get("extra_info", {})
    for d in r:
        assert d["timestamp"] == 0
        assert d["passed"] is True
