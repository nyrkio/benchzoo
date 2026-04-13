# Benchmark Zoo

Benchmark Zoo is the definitive collection on every benchmark framework
out there. We implemented the same simple dummy benchmark in
42 different perf test frameworks, load testers, even unit testing frameworks.


The outputs of each benchmarking tool are stored in [`tests/data`]('tests/data`).


Finally, we used those outputs to generate a parser to go with each of the
benchmark frameworks. Therefore if you need to extract benchmark results
from a log file or from a separate artifact file, then the goal is that
this repository should always have the parser you need.

As a catch-all, there are also two LLM-backed parsers that extract
benchmark results from arbitrary input by prompting an LLM with the
Nyrkiö schema plus a few worked examples from the corpus:

1. `llm_anthropic` — calls the Anthropic API directly. Highest
   accuracy; requires `ANTHROPIC_API_KEY` and `pip install anthropic`.
2. `llm_local` — calls a local [Ollama](https://ollama.com) instance.
   Default model is `qwen2.5-coder:3b`; also works with other small
   coder- or instruction-tuned models (Llama 3.2, Phi-3.5, Gemma 2).
   Offline; deterministic with `temperature=0`.

Both are experimental and non-deterministic by nature. Not appropriate
for production change-detection pipelines; great for triage, one-off
proprietary formats, or bootstrapping a new deterministic parser.
 

## Status

42 frameworks end-to-end (sample benchmark + workflow +
real CI-captured fixture + parser + ground-truth tests); **250+
passing parser tests**. The library is `pip install -e .`-able; the
corpus runs on every push.

Pre-1.0: parser API may still move; not yet on PyPI.

## Install and use

```bash
    pip install -e .

    python -c "
    from benchzoo.parsers import hyperfine_json
    import json

    # Parse whatever output your tool produced
    result = hyperfine_json.parse(open('output.json').read())
    print(json.dumps(result, indent=2))
"
```

Every parser has the same contract: `parse(content: bytes | str) ->
list[dict]`, returning the Nyrkiö JSON shape described in
[`docs/design.md`](docs/design.md).

## Running the tests

```bash
pip install -e ".[dev]"
pytest
```

LLM parser tests skip by default; set `BENCHZOO_RUN_LLM_ANTHROPIC=1`
(+ `ANTHROPIC_API_KEY`) or `BENCHZOO_RUN_LLM_LOCAL=1` to enable them.

## Supported frameworks

### Dedicated benchmark libraries

| Language | Framework | Parser(s) |
| --- | --- | --- |
| Rust | [criterion](frameworks/language/criterion/) | `criterion_estimates`, `criterion_bencher` |
| Rust | [cargo bench (libtest)](frameworks/language/cargo-bench/) | `cargo_bench_libtest` (shares `criterion_bencher`) |
| C++ | [Google Benchmark](frameworks/language/google-benchmark/) | `google_benchmark_json`, `google_benchmark_csv` |
| C++ | [Catch2](frameworks/language/catch2/) | `catch2_xml`, `junit_catch2` |
| Java/JVM | [JMH](frameworks/language/jmh/) | `jmh_json`, `jmh_csv` |
| C# / .NET | [BenchmarkDotNet](frameworks/language/benchmarkdotnet/) | `benchmarkdotnet_json`, `benchmarkdotnet_csv` |
| Go | [`go test -bench`](frameworks/language/go-test-bench/) | `go_bench_text`, `go_bench_json` |
| Python | [pytest-benchmark](frameworks/language/pytest-benchmark/) | `pytest_benchmark_json`, `junit_pytest` |
| Python | [asv (airspeed velocity)](frameworks/language/asv/) | `asv` |
| JS | [benchmark.js](frameworks/language/benchmark-js/) | `benchmark_js` |
| JS | [tinybench](frameworks/language/tinybench/) | `tinybench` |
| JS | [mitata](frameworks/language/mitata/) | `mitata` |
| JS/TS | [vitest bench](frameworks/language/vitest-bench/) | `vitest_bench` |
| Julia | [BenchmarkTools.jl](frameworks/language/benchmarktools-jl/) | `benchmarktools_jl` |
| PHP | [PHPBench](frameworks/language/phpbench/) | `phpbench_xml` |
| Ruby | [benchmark-ips](frameworks/language/benchmark-ips/) | `benchmark_ips` |

### Load / HTTP testing

| Framework | Parser(s) |
| --- | --- |
| [k6](frameworks/loadtest/k6/) | `k6_summary`, `k6_ndjson` |
| [wrk](frameworks/loadtest/wrk/) | `wrk` |
| [wrk2](frameworks/loadtest/wrk2/) | `wrk2` |
| [hey](frameworks/loadtest/hey/) | `hey` |
| [vegeta](frameworks/loadtest/vegeta/) | `vegeta_json` |
| [Locust](frameworks/loadtest/locust/) | `locust_csv` |
| [JMeter](frameworks/loadtest/jmeter/) | `jmeter_csv` |
| [Gatling](frameworks/loadtest/gatling/) | `gatling_log` |

### Databases

| Framework | Parser(s) |
| --- | --- |
| [pgbench](frameworks/database/pgbench/) | `pgbench` |
| [sysbench](frameworks/database/sysbench/) | `sysbench` |
| [redis-benchmark](frameworks/database/redis-benchmark/) | `redis_benchmark_csv` |
| [memtier_benchmark](frameworks/database/memtier/) | `memtier_json` |
| [ClickBench](frameworks/database/clickbench/) | `clickbench` |

### Frontend

| Framework | Parser(s) |
| --- | --- |
| [Lighthouse](frameworks/frontend/lighthouse/) | `lighthouse` |

### Unit-test runners (as timing source)

| Framework | Parser(s) |
| --- | --- |
| [mocha (--reporter json)](frameworks/unit-or-qa/mocha/) | `mocha_json` |
| [Jest (jest-junit)](frameworks/unit-or-qa/junit-jest/) | `junit_jest` |
| [go test (gotestsum)](frameworks/unit-or-qa/junit-go/) | `junit_go` |
| [JUnit 5 / Maven Surefire](frameworks/unit-or-qa/junit-vanilla/) | `junit_vanilla` |
| [dotnet test (TRX)](frameworks/unit-or-qa/dotnet-test/) | `dotnet_test_trx` |
| [CTest (--output-junit)](frameworks/unit-or-qa/ctest/) | `junit_ctest` |
| [Playwright](frameworks/unit-or-qa/playwright/) | `playwright_json` |

### Generic / escape hatches

| Framework | Parser(s) |
| --- | --- |
| [hyperfine](frameworks/generic/hyperfine/) | `hyperfine_json`, `hyperfine_csv` |
| [Unix time (bash + GNU)](frameworks/generic/time/) | `time_builtin`, `time_gnu` |
| [perf stat](frameworks/generic/perf-stat/) | `perf_stat_text` |
| [custom JSON](frameworks/generic/custom-json/) | `custom_bigger_is_better`, `custom_smaller_is_better` |
| [custom CSV](frameworks/generic/custom-csv/) | `custom_csv` |

### Optional: LLM fallback parsers

`benchzoo.parsers.llm_anthropic` and `benchzoo.parsers.llm_local` (see
intro above) cover formats that don't match any of the built-in
parsers. Their evaluation harness lives at
[`tests/parsers/test_llm.py`](tests/parsers/test_llm.py) — set
`BENCHZOO_RUN_LLM_ANTHROPIC=1` (+ `ANTHROPIC_API_KEY`) or
`BENCHZOO_RUN_LLM_LOCAL=1` to run it against the real fixture corpus.

## Adding a framework

The process is documented in
[`docs/workflow-conventions.md`](docs/workflow-conventions.md) and the
[Definition of Done](docs/workflow-conventions.md#what-done-looks-like-for-a-framework)
enumerates the six surfaces every framework must ship.

The short version: implement the
[canonical sample benchmark](docs/sample-benchmark.md) (four fixed
tests, the simplest of which sleeps for exactly 2.15 seconds), put it
under `frameworks/<category>/<name>/`, add a `.github/workflows/<name>.yml`
that captures the output as an artifact, write the parser against the
real captured fixture (grep for `2.15` in the output — that's test 1's
wall time), and add ground-truth tests.



## More Documentation

- **Design:** [`docs/design.md`](docs/design.md) — architecture, data model,
  parser contract.
- **Parser targets:** [`docs/parser-targets.md`](docs/parser-targets.md) —
  what's in scope, what's shipped, what's long-tailed.
- **Canonical sample benchmark:** [`docs/sample-benchmark.md`](docs/sample-benchmark.md) —
  the four fixed tests every framework implements.
- **Workflow conventions:** [`docs/workflow-conventions.md`](docs/workflow-conventions.md) —
  CI / `act` conventions for the corpus.


