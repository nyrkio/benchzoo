"""Ground-truth tests for the three custom escape-hatch parsers:
``custom_bigger_is_better``, ``custom_smaller_is_better``, and
``custom_csv``.

The fixtures under ``tests/data/custom-json-output/`` and
``tests/data/custom-csv-output/`` encode the canonical sample-benchmark
values by construction (the emit scripts hard-code them), so we can
assert exact ground-truth numbers rather than tolerance ranges.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import (
    custom_bigger_is_better,
    custom_csv,
    custom_smaller_is_better,
)

JSON_FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "custom-json-output"
CSV_FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "custom-csv-output"


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def bigger_results():
    return custom_bigger_is_better.parse(
        (JSON_FIXTURES / "output-bigger.json").read_text()
    )


@pytest.fixture(scope="module")
def smaller_results():
    return custom_smaller_is_better.parse(
        (JSON_FIXTURES / "output-smaller.json").read_text()
    )


@pytest.fixture(scope="module")
def csv_results():
    return custom_csv.parse((CSV_FIXTURES / "output.csv").read_text())


def _by_test(results: list[dict]) -> dict[str, dict]:
    return {d["attributes"]["test_name"]: d for d in results}


def _metric(d: dict, name: str) -> dict:
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


# ---------------------------------------------------------------------------
# Structural assertions — shared across all three parsers.
# ---------------------------------------------------------------------------

ALL_FIXTURES = ["bigger_results", "smaller_results", "csv_results"]


@pytest.mark.parametrize("results", ALL_FIXTURES)
def test_has_four_test_runs(results, request):
    r = request.getfixturevalue(results)
    assert len(r) == 4
    names = [d["attributes"]["test_name"] for d in r]
    assert names == ["benchmark1", "benchmark2", "benchmark3", "benchmark4"]


@pytest.mark.parametrize("results", ALL_FIXTURES)
def test_timestamp_is_zero(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert d["timestamp"] == 0


@pytest.mark.parametrize("results", ALL_FIXTURES)
def test_git_attributes_absent(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert "git_repo" not in d["attributes"]
        assert "branch" not in d["attributes"]
        assert "git_commit" not in d["attributes"]


@pytest.mark.parametrize("results", ALL_FIXTURES)
def test_passed_defaults_true(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert d["passed"] is True


# ---------------------------------------------------------------------------
# JSON-variant direction assertions.
# ---------------------------------------------------------------------------

def test_bigger_direction_is_higher_is_better(bigger_results):
    for d in bigger_results:
        for m in d["metrics"]:
            assert m["direction"] == "higher_is_better"


def test_smaller_direction_is_lower_is_better(smaller_results):
    for d in smaller_results:
        for m in d["metrics"]:
            assert m["direction"] == "lower_is_better"


# ---------------------------------------------------------------------------
# JSON-variant: one metric per entry, extra_info routing, ground truth.
# ---------------------------------------------------------------------------

def test_bigger_one_metric_per_test_named_after_test(bigger_results):
    for d in bigger_results:
        assert len(d["metrics"]) == 1
        assert d["metrics"][0]["name"] == d["attributes"]["test_name"]


def test_smaller_one_metric_per_test_named_after_test(smaller_results):
    for d in smaller_results:
        assert len(d["metrics"]) == 1
        assert d["metrics"][0]["name"] == d["attributes"]["test_name"]


def test_smaller_benchmark1_is_2_15_seconds(smaller_results):
    """customSmallerIsBetter emits benchmark1 as 2.15 s directly."""
    r = _by_test(smaller_results)
    m = r["benchmark1"]["metrics"][0]
    assert m["value"] == 2.15
    assert m["unit"] == "s"
    assert m["direction"] == "lower_is_better"


def test_bigger_benchmark1_is_reciprocal(bigger_results):
    """customBiggerIsBetter emits benchmark1's reciprocal: 1/2.15 ≈ 0.4651
    runs/s."""
    r = _by_test(bigger_results)
    m = r["benchmark1"]["metrics"][0]
    assert m["value"] == 0.4651
    assert m["unit"] == "runs/s"
    assert m["direction"] == "higher_is_better"


def test_bigger_extra_is_routed_to_extra_info(bigger_results):
    r = _by_test(bigger_results)
    assert (
        r["benchmark1"]["extra_info"]["extra"]
        == "1 run per 2.15 s canonical sleep"
    )


def test_smaller_extra_is_routed_to_extra_info(smaller_results):
    r = _by_test(smaller_results)
    assert (
        r["benchmark1"]["extra_info"]["extra"]
        == "sleep-dominated; canonical 2.15 s wall time"
    )


# ---------------------------------------------------------------------------
# CSV: grouping, multi-metric tests, optional-column handling, ground truth.
# ---------------------------------------------------------------------------

def test_csv_benchmark1_groups_four_metrics(csv_results):
    r = _by_test(csv_results)
    names = [m["name"] for m in r["benchmark1"]["metrics"]]
    assert names == ["mean", "min", "max", "stddev"]


def test_csv_benchmark1_mean_is_2_15(csv_results):
    r = _by_test(csv_results)
    m = _metric(r["benchmark1"], "mean")
    assert m["value"] == 2.15
    assert m["unit"] == "s"
    assert m["direction"] == "lower_is_better"


def test_csv_benchmark3_mixes_directions_and_units(csv_results):
    """benchmark3 has three ms/lower_is_better latency rows plus one
    MB/s/higher_is_better throughput row in a single test."""
    r = _by_test(csv_results)
    metrics = r["benchmark3"]["metrics"]
    assert len(metrics) == 4
    throughput = _metric(r["benchmark3"], "throughput")
    assert throughput["unit"] == "MB/s"
    assert throughput["direction"] == "higher_is_better"
    assert throughput["value"] == 1400
    mean = _metric(r["benchmark3"], "mean")
    assert mean["unit"] == "ms"
    assert mean["direction"] == "lower_is_better"


def test_csv_empty_unit_and_direction_are_omitted(csv_results):
    """benchmark4's ``month`` row has empty unit and empty direction —
    those keys must be absent from the emitted metric, not set to ``""``."""
    r = _by_test(csv_results)
    month = _metric(r["benchmark4"], "month")
    assert month["value"] == 4
    assert "unit" not in month
    assert "direction" not in month
