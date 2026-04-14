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
    assert [d["test"]["test_name"] for d in results] == [
        "q1", "q2", "q3", "q4", "q5"
    ]


def test_framework_name(results):
    for d in results:
        assert d["env"]["framework"]["name"] == "clickbench"


def test_sut_and_env(results):
    d = results[0]
    assert d["sut"]["name"] == "ClickHouse"
    assert "test_time" in d["run"]
    assert d["test"]["params"]["data_size"] > 0


def test_each_query_has_min_mean_max(results):
    for d in results:
        names = {m["name"] for m in d["metrics"]}
        assert names == {"min", "mean", "max"}
        for m in d["metrics"]:
            assert m["unit"] == "s"
            assert m["direction"] == "lower_is_better"


def test_all_queries_passed(results):
    for d in results:
        assert d["run"]["passed"] is True


def test_query_times_are_sane(results):
    """On a 10k-row synthetic dataset, every query should complete
    in under 1 second (they actually come in around 40 ms each)."""
    for d in results:
        mean = _metric(d, "mean")
        assert 0 < mean["value"] < 1.0, (d["test"]["test_name"], mean)


def test_min_leq_mean_leq_max(results):
    for d in results:
        vmin = _metric(d, "min")["value"]
        vmean = _metric(d, "mean")["value"]
        vmax = _metric(d, "max")["value"]
        assert vmin <= vmean <= vmax


def test_extra_info_populated(results):
    """Corpus-level fields (load_time, tags) are copied into every
    per-query dict's extra_info; cluster_size -> env.cpu_count;
    data_size -> test.params."""
    for d in results:
        ei = d["extra_info"]
        assert d["env"]["cpu_count"] == 1
        assert ei["load_time_s"] > 0
        assert d["test"]["params"]["data_size"] > 0
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
    assert out[0]["run"]["passed"] is True
    assert out[1]["run"]["passed"] is False   # partial failure
    assert out[2]["run"]["passed"] is False   # total failure
    # q3 has no valid runs → no metrics
    assert out[2]["metrics"] == []
