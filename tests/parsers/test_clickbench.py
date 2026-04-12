"""Ground-truth tests for the ClickBench parser.

Fixture at ``tests/data/clickbench-output/`` comes from a real
GitHub Actions run of ``frameworks/database/clickbench``. The 5
queries each ran 3 times against a synthetic 10k-row dataset in
ClickHouse; per-query run times are sub-100ms against that tiny
dataset (the real ClickBench dataset is 70 GB and queries take
seconds).

Unlike most other parsers, we can't assert ~2.15 s here — the
canonical sample-benchmark's test 1/4 sleeps don't map onto SQL
queries. Instead we assert structural properties + sanity ranges.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import clickbench

FIXTURE = (
    pathlib.Path(__file__).parent.parent
    / "data" / "clickbench-output" / "output.json"
)


@pytest.fixture(scope="module")
def results():
    return clickbench.parse(FIXTURE.read_text())


def _metric(d, name):
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


def test_has_five_queries(results):
    assert len(results) == 5
    assert [d["attributes"]["test_name"] for d in results] == [
        "q1", "q2", "q3", "q4", "q5"
    ]


def test_timestamp_is_zero(results):
    for d in results:
        assert d["timestamp"] == 0


def test_git_attributes_absent(results):
    for d in results:
        for key in ("git_repo", "branch", "git_commit"):
            assert key not in d["attributes"]


def test_each_query_has_min_mean_max(results):
    for d in results:
        names = {m["name"] for m in d["metrics"]}
        assert names == {"min", "mean", "max"}
        for m in d["metrics"]:
            assert m["unit"] == "s"
            assert m["direction"] == "lower_is_better"


def test_all_queries_passed(results):
    for d in results:
        assert d["passed"] is True


def test_query_times_are_sane(results):
    """On a 10k-row synthetic dataset, every query should complete
    in under 1 second (they actually come in around 40 ms each)."""
    for d in results:
        mean = _metric(d, "mean")
        assert 0 < mean["value"] < 1.0, (d["attributes"]["test_name"], mean)


def test_min_leq_mean_leq_max(results):
    for d in results:
        vmin = _metric(d, "min")["value"]
        vmean = _metric(d, "mean")["value"]
        vmax = _metric(d, "max")["value"]
        assert vmin <= vmean <= vmax


def test_extra_info_populated(results):
    """Corpus-level fields (system, machine, load_time, data_size)
    are copied into every per-query dict's extra_info."""
    for d in results:
        ei = d["extra_info"]
        assert ei["system"] == "ClickHouse"
        assert ei["cluster_size"] == 1
        assert ei["load_time_s"] > 0
        assert ei["data_size_bytes"] > 0
        assert ei["runs"] == 3
        assert ei["valid_runs"] == 3


def test_parses_failed_runs():
    """A run represented as "nan" or null should mark the test failed."""
    import json
    sample = json.dumps({
        "system": "TestDB",
        "result": [
            [0.1, 0.1, 0.1],       # q1: all ok
            [0.1, "nan", 0.1],     # q2: one failed
            [None, None, None],    # q3: all failed
        ],
    })
    out = clickbench.parse(sample)
    assert out[0]["passed"] is True
    assert out[1]["passed"] is False   # partial failure
    assert out[2]["passed"] is False   # total failure
    # q3 has no valid runs → no metrics
    assert out[2]["metrics"] == []
