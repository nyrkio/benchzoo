"""Ground-truth tests for the JMH JSON and CSV parsers.

The fixtures at ``tests/data/jmh-output/`` are real captured output
from a GitHub Actions run of ``frameworks/language/jmh``. Because the
canonical sample benchmark has known wall times, we can assert the
parsed values fall within expected ranges.

JMH's class-level ``@OutputTimeUnit(TimeUnit.MILLISECONDS)`` combined
with ``@BenchmarkMode(Mode.AverageTime)`` means ``primaryMetric.scoreUnit``
is ``"ms/op"`` in this fixture, so benchmark1's 2.15-second sleep shows
up as ~2150 ms.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import jmh_csv, jmh_json

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "jmh-output"


@pytest.fixture(scope="module")
def json_results():
    return jmh_json.parse((FIXTURES / "output.json").read_text())


@pytest.fixture(scope="module")
def csv_results():
    return jmh_csv.parse((FIXTURES / "output.csv").read_text())


# ---------------------------------------------------------------------------
# Structural assertions — shape of the parsed output.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_has_four_test_runs(results, request):
    r = request.getfixturevalue(results)
    assert len(r) == 4
    names = sorted(d["test"]["test_name"] for d in r)
    assert names == ["benchmark1", "benchmark2", "benchmark3", "benchmark4"]


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_framework_name(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert d["env"]["framework"]["name"] == "jmh"


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_test_name_strips_java_package(results, request):
    """The fixture's benchmark column holds the fully-qualified
    ``io.nyrkio.benchzoo.jmh.SampleBenchmark.benchmarkN``; the parser
    must strip everything up to and including the class name."""
    r = request.getfixturevalue(results)
    for d in r:
        name = d["test"]["test_name"]
        assert "." not in name, f"test_name should not contain dots: {name!r}"
        assert name.startswith("benchmark")
        assert d["test"]["group"] == "io.nyrkio.benchzoo.jmh.SampleBenchmark"


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


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_benchmark1_score_is_2150ms(results, request):
    """benchmark1 sleeps for 2.15 s; scoreUnit is ``ms/op`` so the score
    must land near 2150 ms."""
    r = _by_test(request.getfixturevalue(results))
    score = _metric(r["benchmark1"], "score")
    assert score["unit"] == "ms/op"
    assert 2000 < score["value"] < 2300, score
    assert score["direction"] == "lower_is_better"


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_benchmark1_has_score_error(results, request):
    r = _by_test(request.getfixturevalue(results))
    err = _metric(r["benchmark1"], "score_error")
    assert err["unit"] == "ms/op"
    assert err["value"] is not None
    assert err["value"] >= 0


# ---------------------------------------------------------------------------
# passed flag — no failure signal in either JMH format.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_all_passed(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert d["run"]["passed"] is True


def test_json_jmh_version(json_results):
    assert json_results[0]["env"]["framework"]["version"] == "1.37"


def test_json_runtime_is_jvm(json_results):
    assert "OpenJDK" in json_results[0]["env"]["runtime"]
