"""Ground-truth tests for the JMH rich-text (stdout / CI-log) parser.

The fixture at ``tests/data/jmh-output/output-text.txt`` is a real slice
of a GitHub Actions job *log* for ``frameworks/language/jmh`` (run
27125258764, captured 2026-06-08). Every line therefore carries the
GH-Actions ISO-8601 timestamp prefix and surrounding ``##[group]`` /
maven / JMH-narrative noise — the parser must find the ``Result`` blocks
amid all of it.

Because the run was in **June** (UTC month 6), benchmark4's sleep is
``2.15 + ((6 mod 3) - 1) = 1.15 s``, so it shows up at ~1150 ms — while
benchmark1 is the fixed ~2150 ms sleep.
"""

from __future__ import annotations

import pathlib

import pytest

from benchzoo.parsers import jmh_text

FIXTURES = pathlib.Path(__file__).parent.parent / "data" / "jmh-output"


@pytest.fixture(scope="module")
def text_results():
    return jmh_text.parse((FIXTURES / "output-text.txt").read_text())


def _metric(d: dict, name: str) -> dict:
    for m in d["metrics"]:
        if m["name"] == name:
            return m
    raise AssertionError(f"missing metric {name!r} in {d}")


def _by_test(results: list[dict]) -> dict[str, dict]:
    return {d["test"]["test_name"]: d for d in results}


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

def test_has_four_test_runs(text_results):
    assert len(text_results) == 4
    names = sorted(d["test"]["test_name"] for d in text_results)
    assert names == ["benchmark1", "benchmark2", "benchmark3", "benchmark4"]


def test_framework_name(text_results):
    for d in text_results:
        assert d["env"]["framework"]["name"] == "jmh"


def test_test_name_strips_java_package(text_results):
    for d in text_results:
        name = d["test"]["test_name"]
        assert "." not in name, f"test_name should not contain dots: {name!r}"
        assert name.startswith("benchmark")
        assert d["test"]["group"] == "io.nyrkio.benchzoo.jmh.SampleBenchmark"


def test_all_passed(text_results):
    for d in text_results:
        assert d["run"]["passed"] is True


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------

def test_benchmark1_is_2150ms(text_results):
    """benchmark1 sleeps 2.15 s; unit is ms/op so score ~ 2150 ms."""
    r = _by_test(text_results)
    score = _metric(r["benchmark1"], "score")
    assert score["unit"] == "ms/op"
    assert 2000 < score["value"] < 2300, score
    assert score["direction"] == "lower_is_better"


def test_benchmark1_has_score_error(text_results):
    r = _by_test(text_results)
    err = _metric(r["benchmark1"], "score_error")
    assert err["unit"] == "ms/op"
    assert err["value"] is not None
    assert err["value"] >= 0


def test_benchmark3_is_small_io(text_results):
    """benchmark3 (1.4 MB write) is a few ms; well under benchmark1."""
    r = _by_test(text_results)
    score = _metric(r["benchmark3"], "score")
    assert score["unit"] == "ms/op"
    assert 0 < score["value"] < 100, score
    assert score["direction"] == "lower_is_better"


def test_benchmark2_present_and_nonzero(text_results):
    """benchmark2 (0..1000 loop) is sub-resolution: JMH prints
    ``≈ 10⁻⁴ ms/op``. The parser reports the magnitude so the benchmark
    is present and strictly positive rather than dropped."""
    r = _by_test(text_results)
    score = _metric(r["benchmark2"], "score")
    assert score["unit"] == "ms/op"
    assert score["value"] > 0, score
    assert score["value"] < 1, score  # firmly sub-millisecond


def test_benchmark4_change_point(text_results):
    """benchmark4's sleep cycles {1.15, 2.15, 3.15} s by UTC month; the
    fixture was captured in June (month 6 -> 1.15 s -> ~1150 ms)."""
    r = _by_test(text_results)
    score = _metric(r["benchmark4"], "score")
    assert score["unit"] == "ms/op"
    seconds = score["value"] / 1000.0
    assert min(abs(seconds - v) for v in (1.15, 2.15, 3.15)) < 0.1, score
    # June specifically -> 1.15 s.
    assert 1100 < score["value"] < 1200, score
    assert score["direction"] == "lower_is_better"
