"""Ground-truth tests for the Lighthouse parser.

Unlike the other parsers in the corpus, Lighthouse's sample-benchmark
adaptation is a known deviation (see the framework README): one test
"homepage", not four, and no sleep-based ground-truth assertion. The
tests here check metric-key presence, unit normalization, and that
fetchTime is stashed in extra_info (not used as timestamp).
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import lighthouse

FIXTURE = (
    pathlib.Path(__file__).parent.parent
    / "data" / "lighthouse-output" / "output.json"
)


@pytest.fixture(scope="module")
def results():
    return lighthouse.parse(FIXTURE.read_text())


def _metric(d: dict, name: str) -> dict:
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


def test_single_run_named_homepage(results):
    assert len(results) == 1
    assert results[0]["attributes"]["test_name"] == "homepage"


def test_timestamp_is_zero(results):
    assert results[0]["timestamp"] == 0


def test_git_attributes_absent(results):
    for key in ("git_repo", "branch", "git_commit"):
        assert key not in results[0]["attributes"]


def test_emits_core_web_vitals(results):
    """Parser should surface FCP, LCP, CLS, TBT, Speed Index, TTI."""
    names = {m["name"] for m in results[0]["metrics"]}
    for required in ("fcp", "lcp", "cls", "tbt", "speed_index", "tti"):
        assert required in names, f"missing {required}"


def test_fcp_unit_is_ms_not_verbose_millisecond(results):
    fcp = _metric(results[0], "fcp")
    assert fcp["unit"] == "ms"
    assert fcp["direction"] == "lower_is_better"
    # Sanity: any page loads in at least 1 ms and at most 60 s.
    assert 1 < fcp["value"] < 60_000


def test_fetch_time_in_extra_info_not_timestamp(results):
    """fetchTime is wall-clock and must not be used for Nyrkiö timestamp."""
    assert results[0]["timestamp"] == 0
    assert "fetch_time" in results[0].get("extra_info", {})
    # Sanity: the extra_info value looks like an ISO timestamp.
    assert "T" in results[0]["extra_info"]["fetch_time"]


def test_lighthouse_version_captured(results):
    assert results[0]["extra_info"]["lighthouse_version"] == "12.3.0"


def test_all_passed(results):
    assert results[0]["passed"] is True


def test_missing_audits_are_skipped():
    """Parser must not crash if Lighthouse omits some audits."""
    minimal = '{"audits": {"first-contentful-paint": {"id": "first-contentful-paint", "numericValue": 750, "numericUnit": "millisecond"}}}'
    r = lighthouse.parse(minimal)
    names = {m["name"] for m in r[0]["metrics"]}
    assert names == {"fcp"}
