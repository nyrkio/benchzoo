"""Ground-truth tests for the hyperfine console/stdout text parser.

The fixture ``tests/data/hyperfine-output/output-text.txt`` is a real
slice of a GitHub Actions job log from the ``hyperfine`` workflow
(run 26883187351, captured June 2026). It keeps the ISO-8601 timestamp
prefix, ANSI codes, apt noise, a ``Warning:`` line and the trailing
``Summary`` block so the parser proves it can find the result blocks
amid surrounding noise.

June (UTC month 6) → benchmark4 = 2.15 + ((6 mod 3) - 1) = 1.15 s, and
the log indeed shows 1.157 s.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import hyperfine_text

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "hyperfine-output"


@pytest.fixture(scope="module")
def results():
    return hyperfine_text.parse((FIXTURES / "output-text.txt").read_text())


def _metric(d: dict, name: str) -> dict:
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


def test_four_test_runs(results):
    assert len(results) == 4
    names = [d["test"]["test_name"] for d in results]
    assert names == ["benchmark1", "benchmark2", "benchmark3", "benchmark4"]


def test_framework_stamped(results):
    for d in results:
        assert d["env"]["framework"]["name"] == "hyperfine"


def test_all_passed(results):
    for d in results:
        assert d["run"]["passed"] is True


def test_benchmark1_wall_time_is_215s(results):
    r = {d["test"]["test_name"]: d for d in results}
    mean = _metric(r["benchmark1"], "mean")
    assert 2.0 < mean["value"] < 2.3
    assert mean["unit"] == "s"
    assert mean["direction"] == "lower_is_better"


def test_benchmark2_sub_100ms_nonzero(results):
    r = {d["test"]["test_name"]: d for d in results}
    mean = _metric(r["benchmark2"], "mean")
    # 2.9 ms in the log — must not round to zero, must stay sub-100ms.
    assert 0 < mean["value"] < 0.1
    assert mean["unit"] == "s"


def test_benchmark3_sub_200ms_nonzero(results):
    r = {d["test"]["test_name"]: d for d in results}
    mean = _metric(r["benchmark3"], "mean")
    assert 0 < mean["value"] < 0.2


def test_benchmark4_in_canonical_set(results):
    r = {d["test"]["test_name"]: d for d in results}
    mean = _metric(r["benchmark4"], "mean")
    # June -> 1.15 s; loose check against the {1.15, 2.15, 3.15} cycle.
    assert any(abs(mean["value"] - v) < 0.15 for v in (1.15, 2.15, 3.15))
    # And, for this specific June capture, it is the 1.15 s step.
    assert 1.0 < mean["value"] < 1.3


def test_extra_stats_present(results):
    r = {d["test"]["test_name"]: d for d in results}
    b1 = r["benchmark1"]
    for name in ("mean", "stddev", "min", "max", "user", "system"):
        m = _metric(b1, name)
        assert m["unit"] == "s"
        assert m["direction"] == "lower_is_better"
    # min <= mean <= max sanity.
    assert _metric(b1, "min")["value"] <= _metric(b1, "mean")["value"] <= _metric(b1, "max")["value"]
