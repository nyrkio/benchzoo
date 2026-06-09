"""Ground-truth tests for the asv console (text) parser.

The fixture at ``tests/data/asv-output/output-text.txt`` is a real slice
of the ``asv`` CI job log (run 26995515434, June 2026) — the ``asv run``
progress table plus its surrounding pip/asv-machine noise and the
GitHub-Actions ISO-8601 timestamp prefix on every line.

asv's console table auto-scales units per benchmark (s / ms / μs), so the
parser normalises every value to seconds. Ground truth for that run:

    benchmark1  2.15 s   (sleep 2.15 s)
    benchmark2  54.7 μs  (tight CPU loop)
    benchmark3  5.02 ms  (1.4 MB write)
    benchmark4  1.15 s   (June change-point: 2.15 + ((6 % 3) - 1) = 1.15)
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import asv_text

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "asv-output"


@pytest.fixture(scope="module")
def results():
    return asv_text.parse((FIXTURES / "output-text.txt").read_text())


def _by_test(results):
    return {d["test"]["test_name"]: d for d in results}


def _metric(d: dict, name: str) -> dict:
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


def test_has_four_benchmarks(results):
    assert sorted(d["test"]["test_name"] for d in results) == [
        "benchmark1", "benchmark2", "benchmark3", "benchmark4"
    ]


def test_framework_name(results):
    for d in results:
        assert d["env"]["framework"]["name"] == "asv"


def test_all_passed(results):
    for d in results:
        assert d["run"]["passed"] is True


def test_mean_unit_and_direction(results):
    for d in results:
        m = _metric(d, "mean")
        assert m["unit"] == "s"
        assert m["direction"] == "lower_is_better"


def test_benchmark1_sleep(results):
    # ~2.15 s sleep, parsed from "2.15±0s".
    m = _metric(_by_test(results)["benchmark1"], "mean")
    assert 2.0 <= m["value"] <= 2.3


def test_benchmark4_change_point(results):
    # June: 2.15 + ((6 % 3) - 1) = 1.15 s, parsed from "1.15±0s".
    m = _metric(_by_test(results)["benchmark4"], "mean")
    assert m["value"] == pytest.approx(1.15, abs=0.05)
    # always one of the showcase values
    assert any(abs(m["value"] - v) < 0.05 for v in (1.15, 2.15, 3.15))


def test_benchmark2_submillisecond_nonzero(results):
    # "54.7±0μs" -> 54.7e-6 s, must NOT round to zero.
    m = _metric(_by_test(results)["benchmark2"], "mean")
    assert m["value"] > 0
    assert m["value"] == pytest.approx(54.7e-6, rel=0.01)


def test_benchmark3_small_write_nonzero(results):
    # "5.02±0ms" -> 5.02e-3 s.
    m = _metric(_by_test(results)["benchmark3"], "mean")
    assert m["value"] > 0
    assert m["value"] == pytest.approx(5.02e-3, rel=0.01)


def test_err_metric_present_and_zero_with_quick(results):
    # --quick takes a single sample, so the ±err term is 0.
    for d in results:
        m = _metric(d, "err")
        assert m["unit"] == "s"
        assert m["value"] == 0.0
