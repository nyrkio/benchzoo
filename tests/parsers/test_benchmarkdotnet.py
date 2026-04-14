"""Ground-truth tests for BenchmarkDotNet JSON and CSV parsers.

Fixtures come from a real GitHub Actions run of
``frameworks/language/benchmarkdotnet``. benchmark1's mean should be
~2.15e9 ns (≈ 2.15 seconds) — see the canonical sample-benchmark spec.

The JSON exporter emits raw nanoseconds; the CSV exporter emits
localized strings like ``"2,150,230.74 μs"`` which the CSV parser
converts to ns. Both parsers therefore produce metrics with unit
``"ns"``, and the ground-truth assertions are identical.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import benchmarkdotnet_csv, benchmarkdotnet_json

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "benchmarkdotnet-output"


@pytest.fixture(scope="module")
def json_results():
    return benchmarkdotnet_json.parse((FIXTURES / "output.json").read_text())


@pytest.fixture(scope="module")
def csv_results():
    return benchmarkdotnet_csv.parse((FIXTURES / "output.csv").read_text())


def _metric(d: dict, name: str) -> dict:
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


def _by_test(results: list[dict]) -> dict[str, dict]:
    return {d["test"]["test_name"]: d for d in results}


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_has_four_runs_named_benchmark1_through_4(results, request):
    r = request.getfixturevalue(results)
    assert len(r) == 4
    assert sorted(d["test"]["test_name"] for d in r) == [
        "benchmark1", "benchmark2", "benchmark3", "benchmark4"
    ]


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_framework_name(results, request):
    for d in request.getfixturevalue(results):
        assert d["env"]["framework"]["name"] == "benchmarkdotnet"


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_method_name_lowercased(results, request):
    """BenchmarkDotNet emits PascalCase method names; parser normalizes."""
    for d in request.getfixturevalue(results):
        assert d["test"]["test_name"][0].islower()


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_benchmark1_mean_approx_2_15_seconds(results, request):
    """benchmark1 sleeps 2.15 s; mean in ns should be ~2.15e9."""
    r = _by_test(request.getfixturevalue(results))
    mean = _metric(r["benchmark1"], "mean")
    assert 2.0e9 <= mean["value"] <= 2.3e9, mean
    assert mean["unit"] == "ns"
    assert mean["direction"] == "lower_is_better"


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_benchmark4_mean_in_sleep_range(results, request):
    """benchmark4 sleeps 1.15, 2.15, or 3.15 s depending on UTC month."""
    r = _by_test(request.getfixturevalue(results))
    mean = _metric(r["benchmark4"], "mean")
    assert 1.0e9 <= mean["value"] <= 3.3e9, mean


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_all_passed(results, request):
    for d in request.getfixturevalue(results):
        assert d["run"]["passed"] is True


def test_json_carries_host_env(json_results):
    env = json_results[0]["env"]
    assert env["framework"]["version"] == "0.14.0"
    assert "AMD EPYC" in env["cpu"]
    assert env["cpu_count"] == 2
    assert "Ubuntu" in env["os"]
    assert ".NET" in env["runtime"]


def test_json_group_is_full_type_path(json_results):
    for d in json_results:
        assert d["test"]["group"] == "BenchzooSample.SampleBenchmark"


# Parser-specific: CSV's unit-parsing must handle "μs" (U+03BC)
def test_csv_handles_micro_sign(csv_results):
    """The real fixture uses U+03BC μ (Greek mu); regression guard."""
    r = _by_test(csv_results)
    # benchmark1.mean should be around 2.15e9 ns, which was "~2,150,230 μs"
    mean = _metric(r["benchmark1"], "mean")
    assert mean["value"] > 1e9
