"""Ground-truth tests for the pgbench and sysbench text parsers.

The fixtures at ``tests/data/pgbench-output/`` and
``tests/data/sysbench-output/`` are real captured output from GitHub
Actions runs of the corresponding frameworks. The canonical sample
benchmark has known wall times, so we can assert the parsed values
fall within expected ranges.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import pgbench, sysbench

DATA = pathlib.Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def pgbench_results():
    return pgbench.parse((DATA / "pgbench-output" / "output.txt").read_text())


@pytest.fixture(scope="module")
def sysbench_results():
    return sysbench.parse((DATA / "sysbench-output" / "output.txt").read_text())


def _metric(d: dict, name: str) -> dict:
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


def _by_test(results: list[dict]) -> dict[str, dict]:
    return {d["attributes"]["test_name"]: d for d in results}


# ---------------------------------------------------------------------------
# Structural assertions — both parsers must meet the common contract.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("results", ["pgbench_results", "sysbench_results"])
def test_four_test_runs(results, request):
    r = request.getfixturevalue(results)
    assert len(r) == 4
    names = [d["attributes"]["test_name"] for d in r]
    assert names == ["benchmark1", "benchmark2", "benchmark3", "benchmark4"]


@pytest.mark.parametrize("results", ["pgbench_results", "sysbench_results"])
def test_timestamp_is_zero(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert d["timestamp"] == 0


@pytest.mark.parametrize("results", ["pgbench_results", "sysbench_results"])
def test_git_attributes_absent(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert "git_repo" not in d["attributes"]
        assert "branch" not in d["attributes"]
        assert "git_commit" not in d["attributes"]


@pytest.mark.parametrize("results", ["pgbench_results", "sysbench_results"])
def test_test_name_set(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert d["attributes"]["test_name"]


# ---------------------------------------------------------------------------
# pgbench-specific ground truth.
# ---------------------------------------------------------------------------

def test_pgbench_benchmark1_latency_near_2150ms(pgbench_results):
    r = _by_test(pgbench_results)
    lat = _metric(r["benchmark1"], "latency_average")
    assert 2000 < lat["value"] < 2300, lat
    assert lat["unit"] == "ms"
    assert lat["direction"] == "lower_is_better"


def test_pgbench_benchmark4_latency_in_range(pgbench_results):
    """benchmark4 sleeps for 1.15, 2.15, or 3.15 s depending on UTC month."""
    r = _by_test(pgbench_results)
    lat = _metric(r["benchmark4"], "latency_average")
    assert 1000 < lat["value"] < 3300, lat


def test_pgbench_extra_info_populated(pgbench_results):
    for d in pgbench_results:
        assert "extra_info" in d
        assert d["extra_info"].get("clients") == 1
        assert d["extra_info"].get("threads") == 1
        assert d["extra_info"].get("query_mode") == "simple"


def test_pgbench_all_passed(pgbench_results):
    # All four blocks in the fixture include both latency and a tps line.
    for d in pgbench_results:
        assert d["passed"] is True, d


def test_pgbench_has_tps(pgbench_results):
    """Each block should carry at least one tps metric."""
    for d in pgbench_results:
        names = [m["name"] for m in d["metrics"]]
        assert any(n.startswith("tps") for n in names), names


def test_pgbench_test_name_from_transaction_type(pgbench_results):
    """test_name should come from ``transaction type: benchmarkN.sql``
    (stripping ``.sql``), not just the ``=== benchmarkN ===`` marker."""
    names = [d["attributes"]["test_name"] for d in pgbench_results]
    assert names == ["benchmark1", "benchmark2", "benchmark3", "benchmark4"]


def test_pgbench_missing_metrics_marks_failed():
    """If a block is missing both latency and tps, passed must be False."""
    broken = (
        "=== benchmark1 ===\n"
        "pgbench (16.0)\n"
        "connection to server failed\n"
        "=== benchmark2 ===\n"
        "transaction type: benchmark2.sql\n"
        "scaling factor: 1\n"
        "query mode: simple\n"
        "number of clients: 1\n"
        "number of threads: 1\n"
        "latency average = 5.0 ms\n"
        "tps = 200.0 (without initial connection time)\n"
    )
    res = pgbench.parse(broken)
    assert len(res) == 2
    assert res[0]["passed"] is False
    assert res[0]["metrics"] == []
    assert res[1]["passed"] is True


# ---------------------------------------------------------------------------
# sysbench-specific ground truth.
# ---------------------------------------------------------------------------

def test_sysbench_benchmark1_latency_near_2150ms(sysbench_results):
    r = _by_test(sysbench_results)
    avg = _metric(r["benchmark1"], "latency_avg")
    assert 2000 < avg["value"] < 2300, avg
    assert avg["unit"] == "ms"
    assert avg["direction"] == "lower_is_better"


def test_sysbench_benchmark1_total_time_near_2_15s(sysbench_results):
    r = _by_test(sysbench_results)
    tt = _metric(r["benchmark1"], "total_time")
    assert 2.0 < tt["value"] < 2.3, tt
    assert tt["unit"] == "s"
    assert tt["direction"] == "lower_is_better"


def test_sysbench_benchmark1_latency_fields_all_equal(sysbench_results):
    """With --events=1, min/avg/max/sum all come from the same sample."""
    r = _by_test(sysbench_results)
    b1 = r["benchmark1"]
    values = {
        _metric(b1, n)["value"]
        for n in ("latency_min", "latency_avg", "latency_max", "latency_sum")
    }
    assert len(values) == 1, values


def test_sysbench_all_metrics_present(sysbench_results):
    for d in sysbench_results:
        names = [m["name"] for m in d["metrics"]]
        for n in (
            "latency_min",
            "latency_avg",
            "latency_max",
            "latency_p95",
            "latency_sum",
            "total_time",
        ):
            assert n in names, (d["attributes"]["test_name"], names)


def test_sysbench_extra_info_events(sysbench_results):
    for d in sysbench_results:
        assert d["extra_info"]["number_of_events"] == 1


def test_sysbench_all_passed(sysbench_results):
    for d in sysbench_results:
        assert d["passed"] is True
