"""Ground-truth tests for the pytest-benchmark JSON parser.

The fixture at ``tests/data/pytest-benchmark-output/output.json`` is
real captured output from a GitHub Actions run of
``frameworks/language/pytest-benchmark``. Because the canonical sample
benchmark has known wall times, we assert parsed values fall within
expected ranges.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import pytest_benchmark_json

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "pytest-benchmark-output"


@pytest.fixture(scope="module")
def results():
    return pytest_benchmark_json.parse((FIXTURES / "output.json").read_text())


def _metric(d: dict, name: str) -> dict:
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


def _by_test(results: list[dict]) -> dict[str, dict]:
    return {d["attributes"]["test_name"]: d for d in results}


# ---------------------------------------------------------------------------
# Structural assertions.
# ---------------------------------------------------------------------------

def test_has_four_test_runs(results):
    assert len(results) == 4
    names = [d["attributes"]["test_name"] for d in results]
    assert names == ["benchmark1", "benchmark2", "benchmark3", "benchmark4"]


def test_timestamp_is_zero(results):
    for d in results:
        assert d["timestamp"] == 0, "parsers must set timestamp=0 per design.md"


def test_git_attributes_absent(results):
    for d in results:
        assert "git_repo" not in d["attributes"]
        assert "branch" not in d["attributes"]
        assert "git_commit" not in d["attributes"]


def test_all_passed(results):
    for d in results:
        assert d["passed"] is True


# ---------------------------------------------------------------------------
# Ground-truth assertions — values match what the sample benchmark ran.
# ---------------------------------------------------------------------------

def test_benchmark1_mean_around_215s(results):
    r = _by_test(results)
    mean = _metric(r["benchmark1"], "mean")
    assert 2.0 < mean["value"] < 2.3, mean
    assert mean["unit"] == "s"
    assert mean["direction"] == "lower_is_better"


def test_benchmark2_very_fast(results):
    r = _by_test(results)
    mean = _metric(r["benchmark2"], "mean")
    assert 0 < mean["value"] < 0.01, mean
    assert mean["unit"] == "s"


def test_benchmark3_sub_50ms(results):
    r = _by_test(results)
    mean = _metric(r["benchmark3"], "mean")
    assert 0 < mean["value"] < 0.05, mean


def test_benchmark4_in_range(results):
    r = _by_test(results)
    mean = _metric(r["benchmark4"], "mean")
    assert 1.0 < mean["value"] < 3.3, mean


# ---------------------------------------------------------------------------
# Group handling — from extra_info.
# ---------------------------------------------------------------------------

def test_groups_assigned(results):
    r = _by_test(results)
    assert r["benchmark1"]["extra_info"]["group"] == "sleep"
    assert r["benchmark4"]["extra_info"]["group"] == "sleep"
    assert r["benchmark2"]["extra_info"]["group"] == "compute"
    assert r["benchmark3"]["extra_info"]["group"] == "compute"


# ---------------------------------------------------------------------------
# ops metric — throughput, higher is better.
# ---------------------------------------------------------------------------

def test_benchmark1_ops(results):
    r = _by_test(results)
    ops = _metric(r["benchmark1"], "ops")
    assert ops["unit"] == "ops/s"
    assert ops["direction"] == "higher_is_better"
    # 1/2.15 ≈ 0.465
    assert 0.43 < ops["value"] < 0.50, ops
