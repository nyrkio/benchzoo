"""Ground-truth tests for the bash builtin and GNU /usr/bin/time parsers.

The fixtures at ``tests/data/time-output/`` are captured output from
``frameworks/generic/time/run.sh`` running the canonical sample
benchmark under both the bash builtin ``time`` and ``/usr/bin/time -v``.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import time_builtin, time_gnu

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "time-output"


@pytest.fixture(scope="module")
def builtin_results():
    return time_builtin.parse((FIXTURES / "output-builtin.txt").read_text())


@pytest.fixture(scope="module")
def gnu_results():
    return time_gnu.parse((FIXTURES / "output-gnu.txt").read_text())


def _metric(d: dict, name: str) -> dict:
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


# ---------------------------------------------------------------------------
# time_builtin — v2 schema
# ---------------------------------------------------------------------------

def _b_by_test(results):
    return {d["test"]["test_name"]: d for d in results}


def test_builtin_has_four_test_runs(builtin_results):
    assert len(builtin_results) == 4
    names = [d["test"]["test_name"] for d in builtin_results]
    assert names == ["benchmark1", "benchmark2", "benchmark3", "benchmark4"]


def test_builtin_framework_name(builtin_results):
    for d in builtin_results:
        assert d["env"]["framework"]["name"] == "time"


def test_builtin_test_name_set(builtin_results):
    for d in builtin_results:
        assert d["test"]["test_name"]


def test_builtin_all_passed(builtin_results):
    for d in builtin_results:
        assert d["run"]["passed"] is True


def test_builtin_benchmark1_wall_time_is_215s(builtin_results):
    r = _b_by_test(builtin_results)
    wall = _metric(r["benchmark1"], "real")
    assert 2.0 < wall["value"] < 2.3, wall
    assert wall["unit"] == "s"
    assert wall["direction"] == "lower_is_better"


def test_builtin_benchmark4_wall_time_in_range(builtin_results):
    """benchmark4 sleeps 1.15, 2.15, or 3.15 depending on month."""
    r = _b_by_test(builtin_results)
    wall = _metric(r["benchmark4"], "real")
    assert 1.0 < wall["value"] < 3.3, wall


def test_builtin_has_real_user_sys(builtin_results):
    for d in builtin_results:
        for name in ("real", "user", "sys"):
            m = _metric(d, name)
            assert m["unit"] == "s"
            assert m["direction"] == "lower_is_better"
            assert isinstance(m["value"], float)


# ---------------------------------------------------------------------------
# time_gnu — v2 schema
# ---------------------------------------------------------------------------

def _g_by_test(results):
    return {d["test"]["test_name"]: d for d in results}


def test_gnu_has_four_test_runs(gnu_results):
    assert len(gnu_results) == 4
    names = [d["test"]["test_name"] for d in gnu_results]
    assert names == ["benchmark1", "benchmark2", "benchmark3", "benchmark4"]


def test_gnu_framework_name(gnu_results):
    for d in gnu_results:
        assert d["env"]["framework"]["name"] == "time"


def test_gnu_test_name_set(gnu_results):
    for d in gnu_results:
        assert d["test"]["test_name"]


def test_gnu_all_passed(gnu_results):
    for d in gnu_results:
        assert d["run"]["passed"] is True


def test_gnu_benchmark1_wall_time_is_215s(gnu_results):
    r = _g_by_test(gnu_results)
    wall = _metric(r["benchmark1"], "elapsed")
    assert 2.0 < wall["value"] < 2.3, wall
    assert wall["unit"] == "s"
    assert wall["direction"] == "lower_is_better"


def test_gnu_benchmark4_wall_time_in_range(gnu_results):
    r = _g_by_test(gnu_results)
    wall = _metric(r["benchmark4"], "elapsed")
    assert 1.0 < wall["value"] < 3.3, wall


def test_gnu_has_full_metric_set(gnu_results):
    expected = {
        "elapsed",
        "user",
        "system",
        "cpu_percent",
        "max_rss",
        "page_faults_major",
        "page_faults_minor",
        "voluntary_context_switches",
        "involuntary_context_switches",
        "exit_status",
    }
    for d in gnu_results:
        names = {m["name"] for m in d["metrics"]}
        assert expected <= names, f"missing from {d['test']['test_name']}: {expected - names}"


def test_gnu_max_rss_unit_kb(gnu_results):
    for d in gnu_results:
        m = _metric(d, "max_rss")
        assert m["unit"] == "kB"
        assert m["value"] > 0


def test_gnu_cpu_percent_has_no_direction(gnu_results):
    for d in gnu_results:
        m = _metric(d, "cpu_percent")
        assert m["unit"] == "%"
        assert "direction" not in m, "cpu_percent has no universally-agreed direction"


def test_gnu_benchmark1_max_rss_ground_truth(gnu_results):
    r = _g_by_test(gnu_results)
    m = _metric(r["benchmark1"], "max_rss")
    assert m["value"] == 3476


def test_gnu_benchmark1_minor_page_faults_ground_truth(gnu_results):
    r = _g_by_test(gnu_results)
    m = _metric(r["benchmark1"], "page_faults_minor")
    assert m["value"] == 298


def test_gnu_exit_status_zero_means_passed(gnu_results):
    for d in gnu_results:
        exit_m = _metric(d, "exit_status")
        assert exit_m["value"] == 0
        assert d["run"]["passed"] is True
