"""Ground-truth tests for batch 5 parsers.

Covers mocha_json, dotnet_test_trx, junit_standard (ctest fixture), playwright_json.
(cypress and ycsb parsers added separately once their CI stabilizes.)
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import (
    dotnet_test_trx,
    junit_standard,
    mocha_json,
    playwright_json,
)

DATA = pathlib.Path(__file__).parent.parent / "data"


def _metric(d, name):
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


def _by_test(results):
    return {d["attributes"]["test_name"]: d for d in results}


def test_mocha_json():
    r = mocha_json.parse((DATA / "mocha-output/output.json").read_text())
    assert {d["test"]["test_name"] for d in r} == {
        "benchmark1", "benchmark2", "benchmark3", "benchmark4"
    }
    by = {d["test"]["test_name"]: d for d in r}
    dur = _metric(by["benchmark1"], "duration")
    assert dur["unit"] == "ms"
    assert 2000 <= dur["value"] <= 2300
    for d in r:
        assert d["env"]["framework"]["name"] == "mocha"
        assert d["run"]["passed"] is True


def test_dotnet_test_trx():
    r = dotnet_test_trx.parse((DATA / "dotnet-test-output/output.trx").read_text())
    # Benchmark1..4 short names after stripping namespace + class.
    names = {d["test"]["test_name"] for d in r}
    assert {"benchmark1", "benchmark2", "benchmark3", "benchmark4"} <= names
    by = {d["test"]["test_name"]: d for d in r}
    dur = _metric(by["benchmark1"], "duration")
    assert dur["unit"] == "s"
    assert 2.0 <= dur["value"] <= 2.3, dur
    for d in r:
        assert d["env"]["framework"]["name"] == "dotnet-test"
        assert d["run"]["passed"] is True
        assert d["test"]["group"] == "BenchzooSample.SampleTests"
    assert "test_time" in r[0]["run"]


def test_junit_standard_ctest():
    r = junit_standard.parse((DATA / "ctest-output/output.xml").read_text())
    assert {d["test"]["test_name"] for d in r} == {
        "benchmark1", "benchmark2", "benchmark3", "benchmark4"
    }
    by = {d["test"]["test_name"]: d for d in r}
    dur = _metric(by["benchmark1"], "duration")
    assert dur["unit"] == "s"
    assert 2.0 <= dur["value"] <= 2.3
    for d in r:
        assert d["env"]["framework"]["name"] == "junit-standard"
        assert d["run"]["passed"] is True


def test_playwright_json():
    r = playwright_json.parse((DATA / "playwright-output/output.json").read_text())
    names = {d["test"]["test_name"] for d in r}
    assert {"benchmark1", "benchmark2", "benchmark3", "benchmark4"} <= names
    by = {d["test"]["test_name"]: d for d in r}
    dur = _metric(by["benchmark1"], "duration")
    assert dur["unit"] == "ms"
    assert 2000 <= dur["value"] <= 2300
    for d in r:
        assert d["env"]["framework"]["name"] == "playwright"
        assert d["run"]["passed"] is True
        # test.params captures the browser project
        params = d["test"].get("params", {})
        assert params.get("project") in ("chromium", None)
