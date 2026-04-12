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


# ---------------------------------------------------------------------------
# Structural assertions — shape of the parsed output.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("results", ["builtin_results", "gnu_results"])
def test_has_four_test_runs(results, request):
    r = request.getfixturevalue(results)
    assert len(r) == 4
    names = [d["attributes"]["test_name"] for d in r]
    assert names == ["benchmark1", "benchmark2", "benchmark3", "benchmark4"]


@pytest.mark.parametrize("results", ["builtin_results", "gnu_results"])
def test_timestamp_is_zero(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert d["timestamp"] == 0, "parsers must set timestamp=0 per design.md"


@pytest.mark.parametrize("results", ["builtin_results", "gnu_results"])
def test_git_attributes_absent(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert "git_repo" not in d["attributes"]
        assert "branch" not in d["attributes"]
        assert "git_commit" not in d["attributes"]


@pytest.mark.parametrize("results", ["builtin_results", "gnu_results"])
def test_test_name_set(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert d["attributes"]["test_name"]  # non-empty


@pytest.mark.parametrize("results", ["builtin_results", "gnu_results"])
def test_all_passed(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert d["passed"] is True


# ---------------------------------------------------------------------------
# Ground-truth assertions — values match what the sample benchmark ran.
# ---------------------------------------------------------------------------

def _metric(d: dict, name: str) -> dict:
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


def _by_test(results: list[dict]) -> dict[str, dict]:
    return {d["attributes"]["test_name"]: d for d in results}


# The two parsers use different metric names for the wall-clock field
# (``real`` for the builtin, ``elapsed`` for GNU). Parametrize both.
@pytest.mark.parametrize(
    "results,wall_metric",
    [
        ("builtin_results", "real"),
        ("gnu_results", "elapsed"),
    ],
)
def test_benchmark1_wall_time_is_215s(results, wall_metric, request):
    """benchmark1 sleeps for 2.15 s; wall time must fall within tolerance."""
    r = _by_test(request.getfixturevalue(results))
    wall = _metric(r["benchmark1"], wall_metric)
    assert 2.0 < wall["value"] < 2.3, wall
    assert wall["unit"] == "s"
    assert wall["direction"] == "lower_is_better"


@pytest.mark.parametrize(
    "results,wall_metric",
    [
        ("builtin_results", "real"),
        ("gnu_results", "elapsed"),
    ],
)
def test_benchmark4_wall_time_in_range(results, wall_metric, request):
    """benchmark4 sleeps 1.15, 2.15, or 3.15 depending on month."""
    r = _by_test(request.getfixturevalue(results))
    wall = _metric(r["benchmark4"], wall_metric)
    assert 1.0 < wall["value"] < 3.3, wall


# ---------------------------------------------------------------------------
# Builtin-specific: real/user/sys metrics all present, lower_is_better.
# ---------------------------------------------------------------------------

def test_builtin_has_real_user_sys(builtin_results):
    for d in builtin_results:
        for name in ("real", "user", "sys"):
            m = _metric(d, name)
            assert m["unit"] == "s"
            assert m["direction"] == "lower_is_better"
            assert isinstance(m["value"], float)


# ---------------------------------------------------------------------------
# GNU-specific: rich metric set with the right units/directions.
# ---------------------------------------------------------------------------

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
        assert expected <= names, f"missing from {d['attributes']['test_name']}: {expected - names}"


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
    """benchmark1 in the captured fixture reports 3476 kB max RSS."""
    r = _by_test(gnu_results)
    m = _metric(r["benchmark1"], "max_rss")
    assert m["value"] == 3476


def test_gnu_benchmark1_minor_page_faults_ground_truth(gnu_results):
    r = _by_test(gnu_results)
    m = _metric(r["benchmark1"], "page_faults_minor")
    assert m["value"] == 298


def test_gnu_exit_status_zero_means_passed(gnu_results):
    for d in gnu_results:
        exit_m = _metric(d, "exit_status")
        assert exit_m["value"] == 0
        assert d["passed"] is True
