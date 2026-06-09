"""Ground-truth tests for criterion parsers.

Fixtures at ``tests/data/criterion-output/`` come from a real CI run
of ``frameworks/language/criterion``. benchmark1 and benchmark4 both
measure ~2.15 s sleeps in nanoseconds.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import criterion_bencher, criterion_estimates, criterion_text

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "criterion-output"


@pytest.fixture(scope="module")
def estimates_results():
    return criterion_estimates.parse_directory(FIXTURES / "output")


@pytest.fixture(scope="module")
def bencher_results():
    return criterion_bencher.parse((FIXTURES / "output-bencher.txt").read_text())


@pytest.fixture(scope="module")
def text_results():
    return criterion_text.parse((FIXTURES / "output-text.txt").read_text())


def _metric(d: dict, name: str) -> dict:
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


# ---------------------------------------------------------------------------
# criterion_bencher (v2 schema)
# ---------------------------------------------------------------------------

def _b_by_test(results):
    return {d["test"]["test_name"]: d for d in results}


def test_bencher_has_four(bencher_results):
    assert len(bencher_results) == 4
    assert sorted(d["test"]["test_name"] for d in bencher_results) == [
        "benchmark1", "benchmark2", "benchmark3", "benchmark4"
    ]


def test_bencher_framework_name(bencher_results):
    for d in bencher_results:
        assert d["env"]["framework"]["name"] == "criterion"


def test_bencher_benchmark1_ns_per_iter_is_2_15_seconds(bencher_results):
    r = _b_by_test(bencher_results)
    nsi = _metric(r["benchmark1"], "ns_per_iter")
    assert 2.0e9 <= nsi["value"] <= 2.3e9, nsi


def test_bencher_benchmark4_in_sleep_range(bencher_results):
    r = _b_by_test(bencher_results)
    duration = _metric(r["benchmark4"], "ns_per_iter")
    assert 1.0e9 <= duration["value"] <= 3.3e9, duration


# ---------------------------------------------------------------------------
# criterion_estimates (v2 schema)
# ---------------------------------------------------------------------------

def _e_by_test(results):
    return {d["test"]["test_name"]: d for d in results}


def test_estimates_has_four(estimates_results):
    assert len(estimates_results) == 4
    assert sorted(d["test"]["test_name"] for d in estimates_results) == [
        "benchmark1", "benchmark2", "benchmark3", "benchmark4"
    ]


def test_estimates_framework_name(estimates_results):
    for d in estimates_results:
        assert d["env"]["framework"]["name"] == "criterion"


def test_estimates_benchmark1_mean_is_2_15_seconds(estimates_results):
    r = _e_by_test(estimates_results)
    mean = _metric(r["benchmark1"], "mean")
    assert 2.0e9 <= mean["value"] <= 2.3e9, mean
    assert mean["unit"] == "ns"
    assert mean["direction"] == "lower_is_better"


def test_estimates_benchmark4_in_sleep_range(estimates_results):
    r = _e_by_test(estimates_results)
    duration = _metric(r["benchmark4"], "mean")
    assert 1.0e9 <= duration["value"] <= 3.3e9, duration


def test_estimates_emits_median_and_stddev(estimates_results):
    """The estimates.json parser exposes more stats than bencher text."""
    for d in estimates_results:
        names = {m["name"] for m in d["metrics"]}
        assert "mean" in names
        assert "median" in names
        assert "std_dev" in names


# parse() without a known filename stubs test_name as "<unknown>"
def test_parse_without_filename_yields_unknown_test_name():
    sample = '{"mean":{"point_estimate":1000,"standard_error":1,"confidence_interval":{"confidence_level":0.95,"lower_bound":1,"upper_bound":1}}}'
    result = criterion_estimates.parse(sample)
    assert result[0]["test"]["test_name"] == "<unknown>"


# ---------------------------------------------------------------------------
# criterion_text (default human-readable stdout)
#
# criterion's layout depends on the benchmark id length: SHORT names print
# "benchmarkN              time:   [...]" on one line; LONG names wrap, with
# the id on its own line and "time:" on the next. Both must parse. Fast
# benches (benchmark2/3) report ns / ps — the latter must not be dropped.
# ---------------------------------------------------------------------------

def _t_by_test(results):
    return {d["test"]["test_name"]: d for d in results}


def test_text_has_four_short_name_benchmarks(text_results):
    assert sorted(d["test"]["test_name"] for d in text_results) == [
        "benchmark1", "benchmark2", "benchmark3", "benchmark4"
    ]


def test_text_framework_name(text_results):
    for d in text_results:
        assert d["env"]["framework"]["name"] == "criterion"


def test_text_benchmark1_is_2_15_seconds(text_results):
    point = _metric(_t_by_test(text_results)["benchmark1"], "time")
    assert 2.0e9 <= point["value"] <= 2.3e9, point   # ~2.15 s in ns
    assert point["unit"] == "ns"
    assert point["direction"] == "lower_is_better"


def test_text_benchmark4_in_sleep_range(text_results):
    v = _metric(_t_by_test(text_results)["benchmark4"], "time")["value"]
    assert 1.0e9 <= v <= 3.3e9, v   # one of {1.15, 2.15, 3.15} s in ns


def test_text_handles_picoseconds_without_dropping(text_results):
    # benchmark3 measures in ps (criterion divides by a huge iteration
    # count). It must normalise to ns, not get rounded away or rejected.
    v = _metric(_t_by_test(text_results)["benchmark3"], "time")["value"]
    assert 0.0 < v < 1.0, v   # ~400 ps -> ~0.4 ns


def test_text_wrapped_long_names():
    # Long ids wrap: id on its own line, "time:" on the next. This is the
    # tursodatabase/turso-style layout the parser was originally written for.
    sample = (
        "Benchmarking FTS Cold Query/cold_query/1000_rows: Analyzing\n"
        "FTS Cold Query/cold_query/1000_rows\n"
        "                        time:   [214.98 µs 215.90 µs 217.69 µs]\n"
    )
    rows = criterion_text.parse(sample)
    assert len(rows) == 1
    assert rows[0]["test"]["test_name"] == "FTS Cold Query/cold_query/1000_rows"
    assert _metric(rows[0], "time")["value"] == pytest.approx(215.90e3)  # µs -> ns
