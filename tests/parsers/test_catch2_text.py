"""Ground-truth tests for the Catch2 console-reporter text parser.

The fixture at ``tests/data/catch2-output/output-text.txt`` is a slice of
a real benchzoo CI job log for ``frameworks/language/catch2`` (captured
June 2026, so benchmark4's sleep is 1.15 s). Every line carries the
GitHub-Actions ISO-8601 timestamp prefix, and the benchmark table is
surrounded by Catch2 chrome (banner, source-file lines, the summary
footer) — the parser must find the four data rows amid all of it.

Catch2's console reporter auto-scales the time unit per benchmark
(``s`` for the sleep tests, ``us`` for the CPU/IO tests); the parser
normalises everything to seconds.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import catch2_text

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "catch2-output"


@pytest.fixture(scope="module")
def results():
    return catch2_text.parse((FIXTURES / "output-text.txt").read_text())


def _by_test(results):
    return {d["test"]["test_name"]: d for d in results}


def _metric(d: dict, name: str) -> dict:
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


def test_four_benchmarks(results):
    assert sorted(d["test"]["test_name"] for d in results) == [
        "benchmark1", "benchmark2", "benchmark3", "benchmark4"
    ]


def test_framework_name(results):
    for d in results:
        assert d["env"]["framework"]["name"] == "catch2"
        assert d["run"]["passed"] is True


def test_benchmark1_mean_is_215s(results):
    d = _by_test(results)["benchmark1"]
    mean = _metric(d, "mean")
    assert mean["unit"] == "s"
    assert mean["direction"] == "lower_is_better"
    assert 2.0 < mean["value"] < 2.3   # known 2.15 s sleep


def test_benchmark4_mean_is_115s(results):
    # Captured in June -> month 6 -> 2.15 + ((6 % 3) - 1) = 1.15 s.
    d = _by_test(results)["benchmark4"]
    mean = _metric(d, "mean")
    assert mean["unit"] == "s"
    assert any(abs(mean["value"] - v) < 0.15 for v in (1.15, 2.15, 3.15))
    assert abs(mean["value"] - 1.15) < 0.15


def test_benchmark2_and_3_present_and_nonzero(results):
    by = _by_test(results)
    for name in ("benchmark2", "benchmark3"):
        mean = _metric(by[name], "mean")
        assert mean["unit"] == "s"
        assert mean["value"] > 0.0
        # CPU loop / 1.4 MB write are sub-millisecond.
        assert mean["value"] < 0.1


def test_mean_bounds_bracket_the_mean(results):
    for d in results:
        mean = _metric(d, "mean")["value"]
        low = _metric(d, "mean_low")["value"]
        high = _metric(d, "mean_high")["value"]
        assert low <= mean <= high or abs(low - mean) < 1e-6 or abs(high - mean) < 1e-6


def test_params_captured(results):
    d = _by_test(results)["benchmark1"]
    assert d["test"]["params"]["samples"] == 3
    assert d["test"]["params"]["iterations"] == 1
