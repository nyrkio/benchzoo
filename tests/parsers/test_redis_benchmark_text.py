"""Ground-truth tests for the redis-benchmark text (default output) parser.

redis-benchmark deviates from the canonical four-benchmark suite: it
hammers a Redis server with built-in command types and reports each as a
separate ``test_name``. So the ground truth here is redis-benchmark's own
characteristic numbers (captured against ``redis:7`` on a CI runner with
50 parallel clients, 100k requests/command):

- throughput in the tens of thousands of ops/s
- sub-2 ms average latency

The fixture ``output-text.txt`` is the real CI artifact captured by the
redis-benchmark workflow (run.sh redirects the text summary to a file,
so it is the uploaded artifact — not the job log — that carries it).
"""

from __future__ import annotations

from pathlib import Path

from benchzoo.parsers.redis_benchmark_text import parse


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "data" / "redis-benchmark-output" / "output-text.txt"
)


def _by_name(results):
    return {r["test"]["test_name"]: r for r in results}


def test_parses_all_commands():
    results = parse(FIXTURE.read_text())
    names = set(_by_name(results))
    # run.sh runs: set,get,incr,lpush,rpush,mset
    assert {"SET", "GET", "INCR", "LPUSH", "RPUSH"} <= names
    # MSET shows up as "MSET (10 keys)" in the text output.
    assert any(n.startswith("MSET") for n in names)
    assert len(results) == 6


def test_set_throughput_and_latency_ground_truth():
    results = parse(FIXTURE.read_text())
    setr = _by_name(results)["SET"]
    assert setr["run"]["passed"] is True
    assert setr["env"]["framework"]["name"] == "redis-benchmark"

    metrics = {m["name"]: m for m in setr["metrics"]}

    tp = metrics["throughput"]
    assert tp["unit"] == "ops/s"
    assert tp["direction"] == "higher_is_better"
    # tens of thousands of ops/s on a CI localhost run.
    assert 5_000 < tp["value"] < 500_000

    avg = metrics["avg_latency"]
    assert avg["unit"] == "ms"
    assert avg["direction"] == "lower_is_better"
    # sub-2 ms average latency; non-zero (parser didn't round to 0).
    assert 0.0 < avg["value"] < 5.0


def test_every_command_has_full_latency_breakdown():
    results = parse(FIXTURE.read_text())
    for r in results:
        names = {m["name"] for m in r["metrics"]}
        assert {
            "throughput",
            "avg_latency", "min_latency", "p50_latency",
            "p95_latency", "p99_latency", "max_latency",
        } <= names
        # min <= avg <= max sanity within each command.
        by = {m["name"]: m["value"] for m in r["metrics"]}
        assert by["min_latency"] <= by["avg_latency"] <= by["max_latency"]


def test_tolerates_github_log_timestamp_prefix():
    # Even though the real fixture is an artifact, the parser must tolerate
    # a GH-Actions ISO-8601 timestamp prefix on every line.
    raw = FIXTURE.read_text()
    prefixed = "\n".join(
        f"2026-04-12T22:07:{i % 60:02d}.1234567Z {ln}"
        for i, ln in enumerate(raw.splitlines())
    )
    results = parse(prefixed)
    setr = _by_name(results)["SET"]
    tp = {m["name"]: m for m in setr["metrics"]}["throughput"]
    assert tp["value"] > 5_000
