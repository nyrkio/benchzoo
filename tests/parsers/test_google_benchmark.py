"""Ground-truth tests for the google-benchmark JSON and CSV parsers.

The fixtures at ``tests/data/google-benchmark-output/`` are real
captured output from a GitHub Actions run of
``frameworks/language/google-benchmark``. Because the canonical sample
benchmark has known wall times, we can assert the parsed values fall
within expected ranges — see the "ground truth values" section of
``docs/sample-benchmark.md``.

Google Benchmark reports wall time in whatever unit the benchmark
registered via ``->Unit(...)`` — our sample uses
``benchmark::kMillisecond``, so ``time_unit`` is ``"ms"``. The
ground-truth assertions convert the reported value to seconds using a
unit table so they stay valid even if a future fixture capture lands in
a different unit.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import google_benchmark_csv, google_benchmark_json

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "google-benchmark-output"


@pytest.fixture(scope="module")
def json_results():
    return google_benchmark_json.parse((FIXTURES / "output.json").read_text())


@pytest.fixture(scope="module")
def csv_results():
    return google_benchmark_csv.parse((FIXTURES / "output.csv").read_text())


# Multiplier from the reported unit to seconds.
_TO_SECONDS = {
    "s": 1.0,
    "ms": 1e-3,
    "us": 1e-6,
    "ns": 1e-9,
}


# ---------------------------------------------------------------------------
# Structural assertions — shape of the parsed output.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_has_four_test_runs(results, request):
    r = request.getfixturevalue(results)
    assert len(r) == 4
    names = [d["test"]["test_name"] for d in r]
    assert names == ["benchmark1", "benchmark2", "benchmark3", "benchmark4"]


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_framework_name(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert d["env"]["framework"]["name"] == "google-benchmark"


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_test_name_set(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert d["test"]["test_name"]  # non-empty


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_metrics_real_and_cpu_time(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        names = [m["name"] for m in d["metrics"]]
        assert "real_time" in names
        assert "cpu_time" in names
        for m in d["metrics"]:
            assert m["direction"] == "lower_is_better"
            assert m["unit"] in _TO_SECONDS


# ---------------------------------------------------------------------------
# Ground-truth assertions — values match what the sample benchmark ran.
# ---------------------------------------------------------------------------

def _metric(d: dict, name: str) -> dict:
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


def _by_test(results: list[dict]) -> dict[str, dict]:
    return {d["test"]["test_name"]: d for d in results}


def _seconds(metric: dict) -> float:
    return metric["value"] * _TO_SECONDS[metric["unit"]]


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_benchmark1_wall_time_is_215s(results, request):
    """benchmark1 sleeps for 2.15 s; real_time must fall within tolerance."""
    r = _by_test(request.getfixturevalue(results))
    real = _metric(r["benchmark1"], "real_time")
    in_seconds = _seconds(real)
    assert 2.0 < in_seconds < 2.3, (real, in_seconds)


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_benchmark2_sub_100ms(results, request):
    """benchmark2 is a tight CPU loop per iteration — sub-millisecond."""
    r = _by_test(request.getfixturevalue(results))
    real = _metric(r["benchmark2"], "real_time")
    in_seconds = _seconds(real)
    assert 0 < in_seconds < 0.1, (real, in_seconds)


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_benchmark3_sub_200ms(results, request):
    """benchmark3 writes 1.4 MB of data to /dev/null per iteration."""
    r = _by_test(request.getfixturevalue(results))
    real = _metric(r["benchmark3"], "real_time")
    in_seconds = _seconds(real)
    assert 0 < in_seconds < 0.2, (real, in_seconds)


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_benchmark4_in_range(results, request):
    """benchmark4 sleeps for 1.15, 2.15, or 3.15 s depending on month."""
    r = _by_test(request.getfixturevalue(results))
    real = _metric(r["benchmark4"], "real_time")
    in_seconds = _seconds(real)
    assert 1.0 < in_seconds < 3.3, (real, in_seconds)


# ---------------------------------------------------------------------------
# passed flag — all four sample benchmarks succeed.
# ---------------------------------------------------------------------------

def test_json_all_passed(json_results):
    for d in json_results:
        assert d["run"]["passed"] is True


def test_csv_all_passed(csv_results):
    for d in csv_results:
        assert d["run"]["passed"] is True


def test_json_context_version_and_sut(json_results):
    d = json_results[0]
    assert d["env"]["framework"]["version"] == "v1.9.1"
    assert d["env"]["cpu_count"] == 2
    assert d["sut"]["name"] == "./build/sample_benchmark"
    assert "test_time" in d["run"]
