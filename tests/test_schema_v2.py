"""Validate v2-schema parsers against docs/schema-v2.schema.json.

Only the parsers that have been converted to v2 are exercised here.
Adding a parser to ``V2_PARSERS`` is the signal that it now emits v2.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from jsonschema import Draft202012Validator

from benchzoo.parsers import (
    asv,
    benchmark_ips,
    benchmark_js,
    benchmarkdotnet_csv,
    benchmarkdotnet_json,
    benchmarktools_jl,
    cargo_bench_libtest,
    catch2_xml,
    clickbench,
    criterion_bencher,
    criterion_estimates,
    custom_bigger_is_better,
    custom_csv,
    custom_smaller_is_better,
    dotnet_test_trx,
    gatling_log,
    go_bench_json,
    go_bench_text,
    google_benchmark_csv,
    google_benchmark_json,
    hey,
    hyperfine_csv,
    hyperfine_json,
    jmeter_csv,
    jmh_csv,
    jmh_json,
    lighthouse,
    junit_go,
    junit_pytest,
    junit_standard,
    k6_ndjson,
    k6_summary,
    locust_csv,
    memtier_json,
    mitata,
    mocha_json,
    perf_stat_text,
    pgbench,
    phpbench_xml,
    playwright_json,
    pytest_benchmark_json,
    redis_benchmark_csv,
    sysbench,
    time_builtin,
    time_gnu,
    tinybench,
    vegeta_json,
    vitest_bench,
    wrk,
    wrk2,
)


ROOT = pathlib.Path(__file__).parent.parent
SCHEMA = json.loads((ROOT / "docs" / "schema-v2.schema.json").read_text())
DATA = ROOT / "tests" / "data"


# Parsers converted to v2 are listed here as (module, fixture_path) pairs.
# Adding a parser to this list is the signal that it now emits v2.
V2_PARSERS = [
    (pytest_benchmark_json, DATA / "pytest-benchmark-output" / "output.json"),
    (hyperfine_json,        DATA / "hyperfine-output" / "output.json"),
    (wrk,                   DATA / "wrk-output" / "output.txt"),
    (wrk2,                  DATA / "wrk2-output" / "output.txt"),
    (hey,                   DATA / "hey-output" / "output.txt"),
    (pgbench,               DATA / "pgbench-output" / "output.txt"),
    (sysbench,              DATA / "sysbench-output" / "output.txt"),
    (perf_stat_text,        DATA / "perf-stat-output" / "output-text.txt"),
    (time_builtin,          DATA / "time-output" / "output-builtin.txt"),
    (time_gnu,              DATA / "time-output" / "output-gnu.txt"),
    (redis_benchmark_csv,   DATA / "redis-benchmark-output" / "output.csv"),
    (memtier_json,          DATA / "memtier-output" / "output.json"),
    (locust_csv,            DATA / "locust-output" / "output_stats.csv"),
    (jmeter_csv,            DATA / "jmeter-output" / "output.csv"),
    (gatling_log,           DATA / "gatling-output" / "output.log"),
    (tinybench,             DATA / "tinybench-output" / "output.json"),
    (mitata,                DATA / "mitata-output" / "output.json"),
    (benchmark_js,          DATA / "benchmark-js-output" / "output.json"),
    (benchmark_ips,         DATA / "benchmark-ips-output" / "output.json"),
    (mocha_json,            DATA / "mocha-output" / "output.json"),
    (playwright_json,       DATA / "playwright-output" / "output.json"),
    (go_bench_text,         DATA / "go-test-bench-output" / "output.txt"),
    (go_bench_json,         DATA / "go-test-bench-output" / "output.json"),
    (criterion_bencher,     DATA / "criterion-output" / "output-bencher.txt"),
    (cargo_bench_libtest,   DATA / "cargo-bench-output" / "output.txt"),
    (vitest_bench,          DATA / "vitest-bench-output" / "output.json"),
    (phpbench_xml,          DATA / "phpbench-output" / "output.xml"),
    (criterion_estimates,   DATA / "criterion-output" / "output" / "benchmark1.json"),
    (custom_bigger_is_better,  DATA / "custom-json-output" / "output-bigger.json"),
    (custom_smaller_is_better, DATA / "custom-json-output" / "output-smaller.json"),
    (custom_csv,            DATA / "custom-csv-output" / "output.csv"),
    (hyperfine_csv,         DATA / "hyperfine-output" / "output.csv"),
    (junit_standard,        DATA / "junit-vanilla-output" / "output.xml"),
    (junit_standard,        DATA / "junit-jest-output" / "output.xml"),
    (junit_standard,        DATA / "ctest-output" / "output.xml"),
    (junit_go,              DATA / "junit-go-output" / "output.xml"),
    (junit_pytest,          DATA / "pytest-benchmark-output" / "output-junit.xml"),
    (benchmarkdotnet_json,  DATA / "benchmarkdotnet-output" / "output.json"),
    (benchmarkdotnet_csv,   DATA / "benchmarkdotnet-output" / "output.csv"),
    (jmh_json,              DATA / "jmh-output" / "output.json"),
    (jmh_csv,               DATA / "jmh-output" / "output.csv"),
    (google_benchmark_json, DATA / "google-benchmark-output" / "output.json"),
    (google_benchmark_csv,  DATA / "google-benchmark-output" / "output.csv"),
    (asv,                   DATA / "asv-output" / "output.json"),
    (dotnet_test_trx,       DATA / "dotnet-test-output" / "output.trx"),
    (clickbench,            DATA / "clickbench-output" / "output.json"),
    (lighthouse,            DATA / "lighthouse-output" / "output.json"),
    (catch2_xml,            DATA / "catch2-output" / "output.xml"),
    (vegeta_json,           DATA / "vegeta-output" / "output.json"),
    (k6_summary,            DATA / "k6-output" / "summary.json"),
    (k6_ndjson,             DATA / "k6-output" / "output.json"),
    (benchmarktools_jl,     DATA / "benchmarktools-jl-output" / "output.json"),
]


def test_schema_is_itself_valid():
    Draft202012Validator.check_schema(SCHEMA)


@pytest.mark.parametrize("parser,fixture", V2_PARSERS, ids=lambda p: getattr(p, "__name__", str(p)))
def test_parser_emits_valid_v2(parser, fixture):
    results = parser.parse(fixture.read_bytes())
    validator = Draft202012Validator(SCHEMA)
    errors: list[str] = []
    for i, run in enumerate(results):
        for err in validator.iter_errors(run):
            errors.append(f"result[{i}] {list(err.absolute_path)}: {err.message}")
    assert not errors, "\n".join(errors)
