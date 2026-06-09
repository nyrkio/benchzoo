"""Ground-truth tests for the JMeter stdout Summariser parser.

JMeter does not implement the canonical four benchmarks (it measures
HTTP request latency under load, not an arbitrary sleep/loop/write —
see ``frameworks/loadtest/jmeter/README.md``). The deterministic
ground truth is therefore the **request count**: the test plan is
10 threads x 100 loops = exactly 1000 requests. Latency numbers are
emergent (runner-dependent) so we assert presence + plausible range,
not tight values.
"""

from pathlib import Path

from benchzoo.parsers.jmeter_text import parse

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "data" / "jmeter-output" / "output-text.txt"
)


def _results():
    return parse(FIXTURE.read_bytes())


def test_single_homepage_result():
    results = _results()
    assert len(results) == 1
    r = results[0]
    assert r["test"]["test_name"] == "homepage"
    assert r["env"]["framework"]["name"] == "jmeter"
    assert r["run"]["passed"] is True


def _metric(r, name):
    return next(m for m in r["metrics"] if m["name"] == name)


def test_request_count_is_ground_truth():
    # 10 threads x 100 loops is under our control -> exactly 1000.
    r = _results()[0]
    total = _metric(r, "total_requests")
    assert total["value"] == 1000.0
    assert total["unit"] == "count"
    assert total["direction"] == "higher_is_better"


def test_no_errors():
    r = _results()[0]
    err = _metric(r, "error_count")
    assert err["value"] == 0.0
    rate = _metric(r, "error_rate")
    assert rate["value"] == 0.0


def test_latency_metrics_present_and_plausible():
    r = _results()[0]
    for name in ("elapsed_mean", "elapsed_min", "elapsed_max"):
        m = _metric(r, name)
        assert m["unit"] == "ms"
        assert m["direction"] == "lower_is_better"
        assert m["value"] >= 0.0
    # Loopback static-page latency is sub-second; max here is 36 ms.
    mx = _metric(r, "elapsed_max")
    assert 0 < mx["value"] < 1000


def test_throughput_metric():
    r = _results()[0]
    tput = _metric(r, "throughput")
    assert tput["unit"] == "req/s"
    assert tput["direction"] == "higher_is_better"
    assert tput["value"] > 0


def test_tolerates_gh_timestamp_prefix_and_ansi():
    # The fixture is a raw GitHub Actions log slice: every line carries an
    # ISO-8601 prefix and some lines carry ANSI codes. Parsing it at all
    # proves the prefix is tolerated.
    assert len(_results()) == 1
