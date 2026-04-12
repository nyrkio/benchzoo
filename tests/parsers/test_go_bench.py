"""Ground-truth tests for the go test -bench text and JSON parsers.

Fixtures at ``tests/data/go-test-bench-output/`` are real captured
output from ``go test -bench`` and ``go test -json`` runs of
``frameworks/language/go-test-bench``. Ground-truth ranges come from
the canonical sample benchmark's known wall times.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import go_bench_json, go_bench_text

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "go-test-bench-output"


@pytest.fixture(scope="module")
def text_results():
    return go_bench_text.parse((FIXTURES / "output.txt").read_text())


@pytest.fixture(scope="module")
def json_results():
    return go_bench_json.parse((FIXTURES / "output.json").read_text())


# ---------------------------------------------------------------------------
# Structural assertions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("results", ["text_results", "json_results"])
def test_has_four_test_runs(results, request):
    r = request.getfixturevalue(results)
    assert len(r) == 4
    names = [d["attributes"]["test_name"] for d in r]
    assert names == ["benchmark1", "benchmark2", "benchmark3", "benchmark4"]


@pytest.mark.parametrize("results", ["text_results", "json_results"])
def test_timestamp_is_zero(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert d["timestamp"] == 0, "parsers must set timestamp=0 per design.md"


@pytest.mark.parametrize("results", ["text_results", "json_results"])
def test_git_attributes_absent(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert "git_repo" not in d["attributes"]
        assert "branch" not in d["attributes"]
        assert "git_commit" not in d["attributes"]


@pytest.mark.parametrize("results", ["text_results", "json_results"])
def test_test_name_set(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert d["attributes"]["test_name"]


@pytest.mark.parametrize("results", ["text_results", "json_results"])
def test_all_passed(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert d["passed"] is True


# ---------------------------------------------------------------------------
# Ground-truth assertions
# ---------------------------------------------------------------------------

def _metric(d: dict, name: str) -> dict:
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


def _by_test(results: list[dict]) -> dict[str, dict]:
    return {d["attributes"]["test_name"]: d for d in results}


@pytest.mark.parametrize("results", ["text_results", "json_results"])
def test_benchmark1_ns_per_op_in_range(results, request):
    """benchmark1 sleeps for 2.15 s; ns/op should be ~2.15e9."""
    r = _by_test(request.getfixturevalue(results))
    m = _metric(r["benchmark1"], "ns_per_op")
    assert 2e9 < m["value"] < 2.3e9, m
    assert m["unit"] == "ns"
    assert m["direction"] == "lower_is_better"


@pytest.mark.parametrize("results", ["text_results", "json_results"])
def test_benchmem_metrics_present(results, request):
    """-benchmem was passed, so every bench line has B/op and allocs/op."""
    r = _by_test(request.getfixturevalue(results))
    for name in ("benchmark1", "benchmark2", "benchmark3", "benchmark4"):
        b = _metric(r[name], "bytes_per_op")
        assert b["unit"] == "B"
        a = _metric(r[name], "allocs_per_op")
        assert a["unit"] == "count"


@pytest.mark.parametrize("results", ["text_results", "json_results"])
def test_benchmark4_in_range(results, request):
    """benchmark4 sleeps for 1.15, 2.15, or 3.15 s depending on month."""
    r = _by_test(request.getfixturevalue(results))
    m = _metric(r["benchmark4"], "ns_per_op")
    assert 1e9 < m["value"] < 3.3e9, m


@pytest.mark.parametrize("results", ["text_results", "json_results"])
def test_benchmark2_fast(results, request):
    """benchmark2 is a tight 1000-iter loop — sub-millisecond."""
    r = _by_test(request.getfixturevalue(results))
    m = _metric(r["benchmark2"], "ns_per_op")
    assert 0 < m["value"] < 1e6, m
