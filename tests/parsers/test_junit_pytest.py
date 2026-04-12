"""Tests for the pytest junit XML parser.

The fixture at ``tests/data/pytest-benchmark-output/output-junit.xml``
is real captured output from the ``pytest-benchmark`` sample benchmark
workflow. In this particular run pytest-benchmark did not emit its
stats into the junit XML — only pytest's own per-test ``time`` attribute
is present — so every testcase exercises the "unit-test runner as a
timing source" fallback path in the parser.

A synthetic fixture with ``<properties>`` is also covered inline so we
can assert the benchmark-stats code path without depending on whether a
specific pytest-benchmark version happens to emit them.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import junit_pytest

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "pytest-benchmark-output"


@pytest.fixture(scope="module")
def results():
    return junit_pytest.parse((FIXTURES / "output-junit.xml").read_text())


def _metric(d: dict, name: str) -> dict:
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


def _by_test(rs: list[dict]) -> dict[str, dict]:
    return {d["attributes"]["test_name"]: d for d in rs}


# ---------------------------------------------------------------------------
# Structural assertions.
# ---------------------------------------------------------------------------

def test_has_at_least_four_test_runs(results):
    # Four sample benchmarks; pytest may add extra setup/teardown
    # testcases, which is fine.
    assert len(results) >= 4


def test_expected_benchmarks_present(results):
    names = {d["attributes"]["test_name"] for d in results}
    for expected in ("benchmark1", "benchmark2", "benchmark3", "benchmark4"):
        assert expected in names, f"missing {expected} in {sorted(names)}"


def test_timestamp_is_zero(results):
    for d in results:
        assert d["timestamp"] == 0, "parsers must set timestamp=0 per design.md"


def test_git_attributes_absent(results):
    for d in results:
        assert "git_repo" not in d["attributes"]
        assert "branch" not in d["attributes"]
        assert "git_commit" not in d["attributes"]


def test_test_name_set(results):
    for d in results:
        assert d["attributes"]["test_name"]  # non-empty


def test_all_our_benchmarks_passed(results):
    by = _by_test(results)
    for name in ("benchmark1", "benchmark2", "benchmark3", "benchmark4"):
        assert by[name]["passed"] is True


def test_metrics_nonempty(results):
    for d in results:
        assert d["metrics"], f"no metrics on {d['attributes']['test_name']!r}"


# ---------------------------------------------------------------------------
# Ground-truth assertions — values match what the sample benchmark ran.
# ---------------------------------------------------------------------------
# This fixture has only pytest's native per-test <testcase time="..."> — the
# pytest-benchmark run embeds the 2.15s sleep inside many rounds, so the
# reported duration is the aggregate wall time of the whole testcase, not
# the per-iteration mean. That aggregate must still be >= 2.15 s (at least
# one full sleep happened) and is typically much larger.

def test_benchmark1_duration_at_least_one_sleep(results):
    """benchmark1 sleeps for 2.15 s; total testcase duration must cover it."""
    r = _by_test(results)
    dur = _metric(r["benchmark1"], "duration")
    assert dur["value"] >= 2.15, dur
    assert dur["unit"] == "s"
    assert dur["direction"] == "lower_is_better"


def test_benchmark1_mean_when_properties_present():
    """Synthetic: when pytest-benchmark emits <properties>, benchmark1.mean
    lands in the 2.0-2.3 range, as unit=s lower_is_better."""
    xml = """<?xml version="1.0"?>
    <testsuites><testsuite name="pytest" tests="1" time="2.2">
      <testcase classname="pkg.mod" name="test_benchmark1" time="2.20">
        <properties>
          <property name="min" value="2.1501" />
          <property name="max" value="2.1599" />
          <property name="mean" value="2.155" />
          <property name="median" value="2.154" />
          <property name="stddev" value="0.002" />
          <property name="rounds" value="5" />
          <property name="iterations" value="1" />
          <property name="ops" value="0.464" />
        </properties>
      </testcase>
    </testsuite></testsuites>"""
    out = junit_pytest.parse(xml)
    assert len(out) == 1
    r = out[0]
    assert r["attributes"]["test_name"] == "benchmark1"
    mean = _metric(r, "mean")
    assert 2.0 < mean["value"] < 2.3, mean
    assert mean["unit"] == "s"
    assert mean["direction"] == "lower_is_better"
    ops = _metric(r, "ops")
    assert ops["unit"] == "ops/s"
    assert ops["direction"] == "higher_is_better"
    assert r["extra_info"]["rounds"] == 5
    assert r["extra_info"]["iterations"] == 1
    assert r["passed"] is True


def test_failure_sets_passed_false():
    xml = """<?xml version="1.0"?>
    <testsuites><testsuite name="pytest" tests="1">
      <testcase classname="pkg" name="test_broken" time="0.01">
        <failure message="boom">AssertionError</failure>
      </testcase>
    </testsuite></testsuites>"""
    out = junit_pytest.parse(xml)
    assert len(out) == 1
    assert out[0]["passed"] is False
    # Still emits the duration metric — failed runs are recorded, not filtered.
    assert _metric(out[0], "duration")["value"] == pytest.approx(0.01)


def test_error_sets_passed_false():
    xml = """<?xml version="1.0"?>
    <testsuites><testsuite name="pytest" tests="1">
      <testcase classname="pkg" name="test_crashed" time="0.01">
        <error message="setup failed">RuntimeError</error>
      </testcase>
    </testsuite></testsuites>"""
    out = junit_pytest.parse(xml)
    assert out[0]["passed"] is False


def test_bytes_input_accepted():
    xml = b"""<?xml version="1.0"?>
    <testsuites><testsuite name="pytest" tests="1">
      <testcase classname="pkg" name="test_x" time="0.5" />
    </testsuite></testsuites>"""
    out = junit_pytest.parse(xml)
    assert out[0]["attributes"]["test_name"] == "x"
    assert _metric(out[0], "duration")["value"] == 0.5
