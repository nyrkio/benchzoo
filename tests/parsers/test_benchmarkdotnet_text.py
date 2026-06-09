"""Ground-truth tests for the BenchmarkDotNet console-text parser.

The fixture ``output-text.txt`` is a slice of a real GitHub Actions job
log (run 27106331957, 2026-06-07) for
``frameworks/language/benchmarkdotnet``. Every line therefore carries an
ISO-8601 timestamp prefix that the parser must tolerate. The slice keeps
surrounding noise — per-benchmark detailed-results blocks (which also
contain ``Mean = ...`` lines that must NOT be mistaken for the table),
histograms, the environment banner, and trailing legends — so the parser
proves it can locate the ``// * Summary *`` markdown table amid the chrome.

Ground truth (canonical sample benchmark): benchmark1 ≈ 2.15 s, and since
the fixture was captured in June, benchmark4 ≈ 1.15 s. All four values are
parsed from the markdown table and normalised to nanoseconds.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import benchmarkdotnet_text

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "benchmarkdotnet-output"


@pytest.fixture(scope="module")
def results():
    return benchmarkdotnet_text.parse((FIXTURES / "output-text.txt").read_text())


def _metric(d: dict, name: str) -> dict:
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


def _by_test(results: list[dict]) -> dict[str, dict]:
    return {d["test"]["test_name"]: d for d in results}


def test_has_four_runs_named_benchmark1_through_4(results):
    assert len(results) == 4
    assert sorted(d["test"]["test_name"] for d in results) == [
        "benchmark1", "benchmark2", "benchmark3", "benchmark4"
    ]


def test_framework_name(results):
    for d in results:
        assert d["env"]["framework"]["name"] == "benchmarkdotnet"


def test_method_name_lowercased(results):
    for d in results:
        assert d["test"]["test_name"][0].islower()


def test_all_passed(results):
    for d in results:
        assert d["run"]["passed"] is True


def test_benchmark1_mean_approx_2_15_seconds(results):
    """benchmark1 sleeps 2.15 s; mean in ns should be ~2.15e9."""
    mean = _metric(_by_test(results)["benchmark1"], "mean")
    assert 2.0e9 <= mean["value"] <= 2.3e9, mean
    assert mean["unit"] == "ns"
    assert mean["direction"] == "lower_is_better"


def test_benchmark4_mean_approx_1_15_seconds(results):
    """Fixture captured in June -> benchmark4 sleeps 1.15 s.

    Loose check also accepts the other two months {2.15, 3.15}.
    """
    mean = _metric(_by_test(results)["benchmark4"], "mean")
    assert 1.0e9 <= mean["value"] <= 3.3e9, mean
    # Exact-for-June: nearest of {1.15, 2.15, 3.15} should be 1.15.
    nearest = min((1.15e9, 2.15e9, 3.15e9), key=lambda x: abs(x - mean["value"]))
    assert nearest == 1.15e9, mean


def test_benchmark2_and_3_present_and_nonzero(results):
    by = _by_test(results)
    for name in ("benchmark2", "benchmark3"):
        mean = _metric(by[name], "mean")
        assert mean["value"] > 0, mean
        assert mean["unit"] == "ns"
        assert mean["direction"] == "lower_is_better"


def test_other_columns_parsed(results):
    """Error / StdDev / Median columns become metrics too."""
    b1 = _by_test(results)["benchmark1"]
    names = {m["name"] for m in b1["metrics"]}
    assert {"mean", "error", "stddev", "median"} <= names
    for m in b1["metrics"]:
        assert m["unit"] == "ns"
        assert m["direction"] == "lower_is_better"
