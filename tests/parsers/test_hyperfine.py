"""Ground-truth tests for the hyperfine JSON and CSV parsers.

The fixtures at ``tests/data/hyperfine-output/`` are real captured
output from a GitHub Actions run of ``frameworks/generic/hyperfine``.
Because the canonical sample benchmark has known wall times, we can
assert the parsed values fall within expected ranges — see the
"ground truth values" section of ``docs/sample-benchmark.md``.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import hyperfine_csv, hyperfine_json

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "hyperfine-output"


@pytest.fixture(scope="module")
def json_results():
    return hyperfine_json.parse((FIXTURES / "output.json").read_text())


@pytest.fixture(scope="module")
def csv_results():
    return hyperfine_csv.parse((FIXTURES / "output.csv").read_text())


# ---------------------------------------------------------------------------
# Structural assertions — shape of the parsed output.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_has_four_test_runs(results, request):
    r = request.getfixturevalue(results)
    assert len(r) == 4
    names = [d["attributes"]["test_name"] for d in r]
    assert names == ["benchmark1", "benchmark2", "benchmark3", "benchmark4"]


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_timestamp_is_zero(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert d["timestamp"] == 0, "parsers must set timestamp=0 per design.md"


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_git_attributes_absent(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert "git_repo" not in d["attributes"]
        assert "branch" not in d["attributes"]
        assert "git_commit" not in d["attributes"]


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_test_name_set(results, request):
    r = request.getfixturevalue(results)
    for d in r:
        assert d["attributes"]["test_name"]  # non-empty


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


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_benchmark1_wall_time_is_215s(results, request):
    """benchmark1 sleeps for 2.15 s; mean must fall within tolerance."""
    r = _by_test(request.getfixturevalue(results))
    mean = _metric(r["benchmark1"], "mean")
    assert 2.0 < mean["value"] < 2.3, mean
    assert mean["unit"] == "s"
    assert mean["direction"] == "lower_is_better"


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_benchmark2_sub_100ms(results, request):
    """benchmark2 is an empty bash for-loop; bash startup dominates.
    On a reasonable runner it's well under 100 ms (typically a few ms)."""
    r = _by_test(request.getfixturevalue(results))
    mean = _metric(r["benchmark2"], "mean")
    assert 0 < mean["value"] < 0.1, mean
    assert mean["unit"] == "s"


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_benchmark3_sub_200ms(results, request):
    """benchmark3 writes 1.4 MB of urandom to /dev/null — fast."""
    r = _by_test(request.getfixturevalue(results))
    mean = _metric(r["benchmark3"], "mean")
    assert 0 < mean["value"] < 0.2, mean


@pytest.mark.parametrize("results", ["json_results", "csv_results"])
def test_benchmark4_in_range(results, request):
    """benchmark4 sleeps for 1.15, 2.15, or 3.15 s depending on month."""
    r = _by_test(request.getfixturevalue(results))
    mean = _metric(r["benchmark4"], "mean")
    assert 1.0 < mean["value"] < 3.3, mean


# ---------------------------------------------------------------------------
# passed flag — JSON should be True (no exit codes), CSV always True.
# ---------------------------------------------------------------------------

def test_json_all_passed(json_results):
    for d in json_results:
        assert d["passed"] is True


def test_csv_all_passed(csv_results):
    for d in csv_results:
        assert d["passed"] is True
