"""Ground-truth tests for the Locust console-summary stdout parser.

Locust does not implement the canonical four benchmarks: it measures one
HTTP endpoint's behavior under sustained concurrent load, and the latency
numbers are emergent (runner-dependent) — see
``frameworks/loadtest/locust/README.md``. So, like ``wrk``/``hey``, the
ground-truth assertions are loose: presence-of-key, unit/direction, and
plausible ranges, not tight numeric bounds.

The fixture is a real slice of the framework's own CI job log (every line
carries a GitHub-Actions ISO-8601 timestamp prefix), so parsing it at all
proves the prefix is tolerated.
"""

from pathlib import Path

from benchzoo.parsers.locust_text import parse

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "data" / "locust-output" / "output-text.txt"
)


def _results():
    return parse(FIXTURE.read_bytes())


def _metric(r, name):
    return next(m for m in r["metrics"] if m["name"] == name)


def test_single_non_aggregate_result():
    # One real endpoint row ("GET /"); the Aggregated rollup is skipped.
    results = _results()
    assert len(results) == 1
    r = results[0]
    assert r["test"]["test_name"] == "GET /"
    assert r["env"]["framework"]["name"] == "locust"
    assert r["run"]["passed"] is True


def test_throughput_is_higher_is_better_and_positive():
    r = _results()[0]
    rps = _metric(r, "requests_per_sec")
    assert rps["unit"] == "ops/s"
    assert rps["direction"] == "higher_is_better"
    # Ground truth from the CI log: ~1585 req/s. Loose but non-zero.
    assert rps["value"] > 0
    assert rps["value"] == 1585.66


def test_latency_metrics_present_unit_and_direction():
    r = _results()[0]
    for name in ("latency_avg", "latency_min", "latency_max",
                 "latency_median", "latency_p50", "latency_p99",
                 "latency_p100"):
        m = _metric(r, name)
        assert m["unit"] == "ms"
        assert m["direction"] == "lower_is_better"
        assert m["value"] > 0
    # Loopback static-page latencies are small (single-to-double-digit ms).
    assert _metric(r, "latency_median")["value"] < 1000
    assert _metric(r, "latency_max")["value"] < 1000


def test_percentiles_monotonic_nondecreasing():
    # p50 <= p99 <= p100 is a structural sanity check that the parser read
    # the percentile columns in order.
    r = _results()[0]
    p50 = _metric(r, "latency_p50")["value"]
    p99 = _metric(r, "latency_p99")["value"]
    p100 = _metric(r, "latency_p100")["value"]
    assert p50 <= p99 <= p100


def test_failures_metric_is_zero_on_happy_path():
    r = _results()[0]
    fps = _metric(r, "failures_per_sec")
    assert fps["unit"] == "ops/s"
    assert fps["direction"] == "lower_is_better"
    assert fps["value"] == 0.0
    assert r["extra_info"]["failure_count"] == 0


def test_request_count_extra_info():
    r = _results()[0]
    # Ground truth from the CI log: 14619 requests.
    assert r["extra_info"]["request_count"] == 14619


def test_tolerates_gh_timestamp_prefix_and_ansi():
    # The fixture is a raw GitHub Actions log slice with ISO-8601 prefixes
    # and ANSI codes on the surrounding noise lines; finding the table at
    # all proves the prefix and noise are tolerated.
    assert len(_results()) == 1
