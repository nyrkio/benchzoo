"""Ground-truth tests for the hyperfine JSON (v2) and CSV (v1) parsers.

The fixtures at ``tests/data/hyperfine-output/`` are real captured
output from a GitHub Actions run of ``frameworks/generic/hyperfine``.

Note: hyperfine_json has been converted to the v2 schema as a demo;
hyperfine_csv is still v1. The two test groups below assert against
their respective shapes.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import hyperfine_csv, hyperfine_json

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "hyperfine-output"


@pytest.fixture(scope="module")
def json_results():
    return hyperfine_json.parse((FIXTURES / "output.json").read_text())


@pytest.fixture(scope="module")
def csv_results():
    return hyperfine_csv.parse((FIXTURES / "output.csv").read_text())


def _metric(d: dict, name: str) -> dict:
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


# ---------------------------------------------------------------------------
# v2 schema — hyperfine_json
# ---------------------------------------------------------------------------


def test_json_has_four_test_runs(json_results):
    assert len(json_results) == 4
    names = [d["test"]["test_name"] for d in json_results]
    assert names == ["benchmark1", "benchmark2", "benchmark3", "benchmark4"]


def test_json_framework_stamped(json_results):
    for d in json_results:
        assert d["env"]["framework"]["name"] == "hyperfine"


def test_json_benchmark1_wall_time_is_215s(json_results):
    r = {d["test"]["test_name"]: d for d in json_results}
    mean = _metric(r["benchmark1"], "mean")
    assert 2.0 < mean["value"] < 2.3
    assert mean["unit"] == "s"
    assert mean["direction"] == "lower_is_better"


def test_json_benchmark2_sub_100ms(json_results):
    r = {d["test"]["test_name"]: d for d in json_results}
    mean = _metric(r["benchmark2"], "mean")
    assert 0 < mean["value"] < 0.1


def test_json_benchmark3_sub_200ms(json_results):
    r = {d["test"]["test_name"]: d for d in json_results}
    mean = _metric(r["benchmark3"], "mean")
    assert 0 < mean["value"] < 0.2


def test_json_benchmark4_in_range(json_results):
    r = {d["test"]["test_name"]: d for d in json_results}
    mean = _metric(r["benchmark4"], "mean")
    assert 1.0 < mean["value"] < 3.3


def test_json_all_passed(json_results):
    for d in json_results:
        assert d["run"]["passed"] is True


# ---------------------------------------------------------------------------
# v1 schema — hyperfine_csv (unconverted)
# ---------------------------------------------------------------------------


def test_csv_has_four_test_runs(csv_results):
    assert len(csv_results) == 4
    names = [d["attributes"]["test_name"] for d in csv_results]
    assert names == ["benchmark1", "benchmark2", "benchmark3", "benchmark4"]


def test_csv_timestamp_is_zero(csv_results):
    for d in csv_results:
        assert d["timestamp"] == 0


def test_csv_benchmark1_wall_time_is_215s(csv_results):
    r = {d["attributes"]["test_name"]: d for d in csv_results}
    mean = _metric(r["benchmark1"], "mean")
    assert 2.0 < mean["value"] < 2.3
    assert mean["unit"] == "s"


def test_csv_all_passed(csv_results):
    for d in csv_results:
        assert d["passed"] is True
