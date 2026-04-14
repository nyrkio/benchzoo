"""Ground-truth tests for the pytest-benchmark JSON parser (v2 schema).

The fixture at ``tests/data/pytest-benchmark-output/output.json`` is
real captured output from a GitHub Actions run of
``frameworks/language/pytest-benchmark``.
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
    return {d["test"]["test_name"]: d for d in results}


def test_has_four_test_runs(results):
    assert len(results) == 4
    names = [d["test"]["test_name"] for d in results]
    assert names == ["benchmark1", "benchmark2", "benchmark3", "benchmark4"]


def test_all_passed(results):
    for d in results:
        assert d["run"]["passed"] is True


def test_commit_populated(results):
    for d in results:
        c = d["commit"]
        assert c["repo"] == "benchzoo"
        assert len(c["sha"]) == 40
        assert c["ref"] == "main"
        assert isinstance(c["commit_time"], int) and c["commit_time"] > 1_700_000_000


def test_run_populated(results):
    for d in results:
        assert isinstance(d["run"]["test_time"], int)


def test_env_populated(results):
    for d in results:
        e = d["env"]
        assert e["os"] == "Linux"
        assert e["arch"] == "x86_64"
        assert "Intel" in e["cpu"] or "Xeon" in e["cpu"]
        assert e["cpu_count"] >= 1
        assert "CPython" in e["runtime"]
        assert e["framework"]["name"] == "pytest-benchmark"


def test_benchmark1_mean_around_215s(results):
    mean = _metric(_by_test(results)["benchmark1"], "mean")
    assert 2.0 < mean["value"] < 2.3
    assert mean["unit"] == "s"
    assert mean["direction"] == "lower_is_better"


def test_benchmark2_very_fast(results):
    mean = _metric(_by_test(results)["benchmark2"], "mean")
    assert 0 < mean["value"] < 0.01


def test_benchmark3_sub_50ms(results):
    mean = _metric(_by_test(results)["benchmark3"], "mean")
    assert 0 < mean["value"] < 0.05


def test_benchmark4_in_range(results):
    mean = _metric(_by_test(results)["benchmark4"], "mean")
    assert 1.0 < mean["value"] < 3.3


def test_groups_in_test_block(results):
    r = _by_test(results)
    assert r["benchmark1"]["test"]["group"] == "sleep"
    assert r["benchmark4"]["test"]["group"] == "sleep"
    assert r["benchmark2"]["test"]["group"] == "compute"
    assert r["benchmark3"]["test"]["group"] == "compute"


def test_benchmark1_ops(results):
    ops = _metric(_by_test(results)["benchmark1"], "ops")
    assert ops["unit"] == "ops/s"
    assert ops["direction"] == "higher_is_better"
    assert 0.43 < ops["value"] < 0.50
