"""Ground-truth tests for batch 4 parsers.

Covers jmeter_csv, gatling_log, wrk2, memtier_json.
(ycsb, cassandra-stress parsers added separately once their CI
stabilizes.)
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import (
    gatling_log,
    jmeter_csv,
    memtier_json,
    wrk2,
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
# JMeter CSV — aggregates per label
# ---------------------------------------------------------------------------

def test_jmeter_csv():
    results = jmeter_csv.parse((DATA / "jmeter-output/output.csv").read_text())
    assert len(results) == 1
    d = results[0]
    assert d["attributes"]["test_name"] == "homepage"
    mean = _metric(d, "elapsed_mean")
    assert mean["unit"] == "ms"
    # localhost nginx — per-request elapsed well under 100 ms
    assert 0 < mean["value"] < 100
    names = {m["name"] for m in d["metrics"]}
    assert "elapsed_p50" not in names  # we emit p90/p95/p99, not p50
    assert "elapsed_p99" in names
    assert d["extra_info"]["samples"] == 1000  # 10 threads × 100 loops
    assert d["passed"] is True
    assert d["timestamp"] == 0


# ---------------------------------------------------------------------------
# Gatling log — REQUEST rows, latency = end_ts - start_ts
# ---------------------------------------------------------------------------

def test_gatling_log():
    results = gatling_log.parse((DATA / "gatling-output/output.log").read_text())
    # At least one test name (whatever the request was named in the simulation)
    assert len(results) >= 1
    d = results[0]
    mean = _metric(d, "latency_mean")
    assert mean["unit"] == "ms"
    # Localhost — single-digit ms typical
    assert 0 <= mean["value"] < 100
    assert d["extra_info"]["samples"] > 0
    assert d["passed"] is True


# ---------------------------------------------------------------------------
# wrk2 — HdrHistogram percentiles
# ---------------------------------------------------------------------------

def test_wrk2():
    results = wrk2.parse((DATA / "wrk2-output/output.txt").read_text())
    assert len(results) == 1
    d = results[0]
    assert d["test"]["test_name"] == "homepage"
    assert d["env"]["framework"]["name"] == "wrk2"
    avg = _metric(d, "latency_avg")
    assert avg["unit"] == "ms"
    assert 0 < avg["value"] < 100
    # wrk2 emits rich percentile list from p50 all the way to p100
    names = {m["name"] for m in d["metrics"]}
    assert "latency_p50" in names
    assert "latency_p99" in names
    assert "latency_p999" in names     # 99.900 → p999
    assert "latency_p9999" in names    # 99.990
    assert d["run"]["passed"] is True


# ---------------------------------------------------------------------------
# memtier JSON — per-op-type dicts
# ---------------------------------------------------------------------------

def test_memtier_json():
    results = memtier_json.parse((DATA / "memtier-output/output.json").read_text())
    names = {d["test"]["test_name"] for d in results}
    # memtier emits at least Sets + Gets + Totals
    assert "sets" in names
    assert "gets" in names
    assert "totals" in names
    by_test = {d["test"]["test_name"]: d for d in results}
    ops = _metric(by_test["totals"], "ops_per_sec")
    assert ops["direction"] == "higher_is_better"
    assert ops["value"] > 100
    mean = _metric(by_test["totals"], "latency_mean")
    assert mean["unit"] == "ms"
    assert mean["direction"] == "lower_is_better"
    for d in results:
        assert d["env"]["framework"]["name"] == "memtier"
        assert d["run"]["passed"] is True
