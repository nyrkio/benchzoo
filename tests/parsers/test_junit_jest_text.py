"""Ground-truth tests for the junit_jest_text parser.

Fixture is a real slice of the junit-jest GitHub Actions job log
(run 26864764044, 2026-06-03), including the npm-install noise above the
Jest default-reporter block so the parser proves it can locate the
per-test lines amid surrounding log chrome. Each line carries the
GH-Actions ISO-8601 timestamp prefix, which the parser must tolerate.

benchmark1 ~ 2.15 s, benchmark4 ~ 1.15 s (June: 2.15 + ((6 mod 3) - 1)),
benchmark2/benchmark3 sub-10 ms but non-zero.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import junit_jest_text

DATA = pathlib.Path(__file__).parent.parent / "data"


def _metric(d, name):
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


@pytest.fixture(scope="module")
def results():
    text = (DATA / "junit-jest-output/output-text.txt").read_text()
    return junit_jest_text.parse(text)


def test_finds_all_four_benchmarks(results):
    names = [r["test"]["test_name"] for r in results]
    assert names == ["benchmark1", "benchmark2", "benchmark3", "benchmark4"]


def test_framework_and_passed(results):
    for r in results:
        assert r["env"]["framework"]["name"] == "junit-jest"
        assert r["run"]["passed"] is True


def test_metric_unit_and_direction(results):
    for r in results:
        m = _metric(r, "duration")
        assert m["unit"] == "s"
        assert m["direction"] == "lower_is_better"


def test_ground_truth_values(results):
    by_name = {r["test"]["test_name"]: r for r in results}

    b1 = _metric(by_name["benchmark1"], "duration")["value"]
    assert 2.0 <= b1 <= 2.3, b1  # ~2.15 s sleep

    b4 = _metric(by_name["benchmark4"], "duration")["value"]
    # June change point: 2.15 + ((6 mod 3) - 1) = 1.15 s; allow the
    # {1.15, 2.15, 3.15} step family with slack.
    assert any(abs(b4 - x) < 0.15 for x in (1.15, 2.15, 3.15)), b4
    assert abs(b4 - 1.15) < 0.15, b4  # this fixture is from June

    # CPU loop + buffer fill: sub-10 ms but recorded non-zero.
    b2 = _metric(by_name["benchmark2"], "duration")["value"]
    b3 = _metric(by_name["benchmark3"], "duration")["value"]
    assert 0.0 < b2 < 0.05, b2
    assert 0.0 < b3 < 0.05, b3
