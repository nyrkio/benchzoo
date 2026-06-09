# Benchmark Zoo

Benchmark Zoo is the definitive collection on every benchmark framework
out there. We implemented the same simple dummy benchmark in
42 different perf test frameworks, load testers, even unit testing frameworks.


The outputs of each benchmarking tool are stored in [`tests/data`](tests/data).


Finally, we used those outputs to generate a parser to go with each of the
benchmark frameworks. Therefore if you need to extract benchmark results
from a log file or from a separate artifact file, then the goal is that
this repository should always have the parser you need.

**And you don't even need to tell benchzoo which parser to use.**
Hand `benchzoo.sniff(content)` any benchmark output — **all 42
supported frameworks are autodetected from content alone**, via a
four-tier signature matcher (JSON top-level keys → XML root element →
CSV header row → distinctive text substring):

> asv, benchmark-ips, benchmark-js, benchmarkdotnet, benchmarktools-jl,
> cargo-bench, catch2, clickbench, custom-csv, custom-json, dotnet-test,
> gatling, go-test-bench, google-benchmark, hey, hyperfine, jmeter, jmh,
> junit-go, junit-standard, k6, lighthouse, locust, memtier, mitata,
> mocha, perf-stat, pgbench, phpbench, playwright, pytest-benchmark,
> redis-benchmark, sysbench, time, tinybench, vegeta, vitest-bench,
> wrk, wrk2.

`junit-standard` covers jest-junit, Maven Surefire / vanilla Java
JUnit, CTest and Catch2's junit reporter — all four emit structurally
indistinguishable `<testsuite>` XML, and a single shared parser reads
testcase `name` + `time` verbatim. gotestsum's junit XML has the same
shape but is distinguished by its `<property name="go.version" ...>`
fingerprint, which routes to `junit-go`'s `Test`-prefix-stripping
parser.

Hard invariant: `sniff` never returns a wrong framework. When content
is genuinely ambiguous it returns `None` and you fall through to
explicit selection or the LLM parsers below.

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
real CI-captured fixture + parser + ground-truth tests); **370+
passing parser tests**. **32 frameworks parse plain stdout / CI-log
output** (the `*_text` parsers) — so results printed to a job log with
no uploaded artifact still ingest. The library is `pip install -e .`-able;
the corpus runs on every push.

Pre-1.0: parser API may still move; not yet on PyPI.

## Install and use

```bash
pip install -e .
```

```python
import benchzoo

content = open("output.json").read()

# 1. Explicit — best when you have out-of-band info (e.g. a CI
#    artifact name, a config setting) that tells you which
#    framework produced `content`.
results = benchzoo.find_parser("hyperfine", "json").parse(content)

# 2. Sniff-based — best-effort content detection. Returns the
#    framework name (string) or None. Never returns a wrong name:
#    when the input is ambiguous, it's None and the caller decides
#    what to do next.
framework = benchzoo.sniff(content)      # e.g. "hyperfine" or None
if framework:
    results = benchzoo.find_parser(framework).parse(content)
else:
    # 3. Catch-all — hand off to the LLM fallback parsers for
    #    formats benchzoo doesn't have a dedicated parser for.
    from benchzoo.parsers import llm_local
    results = llm_local.parse(content)

# Browse the registry directly if you're wiring up your own
# dispatcher.
for framework, formats in benchzoo.PARSERS.items():
    print(framework, list(formats))
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
| C++ | [Catch2](frameworks/language/catch2/) | `catch2_xml`, `junit_standard`, `catch2_text` |
| Java/JVM | [JMH](frameworks/language/jmh/) | `jmh_json`, `jmh_csv`, `jmh_text` |
| C# / .NET | [BenchmarkDotNet](frameworks/language/benchmarkdotnet/) | `benchmarkdotnet_json`, `benchmarkdotnet_csv`, `benchmarkdotnet_text` |
| Go | [`go test -bench`](frameworks/language/go-test-bench/) | `go_bench_text`, `go_bench_json` |
| Python | [pytest-benchmark](frameworks/language/pytest-benchmark/) | `pytest_benchmark_json`, `junit_pytest`, `pytest_benchmark_text` |
| Python | [asv (airspeed velocity)](frameworks/language/asv/) | `asv`, `asv_text` |
| JS | [benchmark.js](frameworks/language/benchmark-js/) | `benchmark_js` |
| JS | [tinybench](frameworks/language/tinybench/) | `tinybench` |
| JS | [mitata](frameworks/language/mitata/) | `mitata`, `mitata_text` |
| JS/TS | [vitest bench](frameworks/language/vitest-bench/) | `vitest_bench`, `vitest_bench_text` |
| Julia | [BenchmarkTools.jl](frameworks/language/benchmarktools-jl/) | `benchmarktools_jl`, `benchmarktools_jl_text` |
| PHP | [PHPBench](frameworks/language/phpbench/) | `phpbench_xml`, `phpbench_text` |
| Ruby | [benchmark-ips](frameworks/language/benchmark-ips/) | `benchmark_ips`, `benchmark_ips_text` |

### Load / HTTP testing

| Framework | Parser(s) |
| --- | --- |
| [k6](frameworks/loadtest/k6/) | `k6_summary`, `k6_ndjson` |
| [wrk](frameworks/loadtest/wrk/) | `wrk` |
| [wrk2](frameworks/loadtest/wrk2/) | `wrk2` |
| [hey](frameworks/loadtest/hey/) | `hey` |
| [vegeta](frameworks/loadtest/vegeta/) | `vegeta_json` |
| [Locust](frameworks/loadtest/locust/) | `locust_csv`, `locust_text` |
| [JMeter](frameworks/loadtest/jmeter/) | `jmeter_csv`, `jmeter_text` |
| [Gatling](frameworks/loadtest/gatling/) | `gatling_log` |

### Databases

| Framework | Parser(s) |
| --- | --- |
| [pgbench](frameworks/database/pgbench/) | `pgbench` |
| [sysbench](frameworks/database/sysbench/) | `sysbench` |
| [redis-benchmark](frameworks/database/redis-benchmark/) | `redis_benchmark_csv`, `redis_benchmark_text` |
| [memtier_benchmark](frameworks/database/memtier/) | `memtier_json`, `memtier_text` |
| [ClickBench](frameworks/database/clickbench/) | `clickbench` |

### Frontend

| Framework | Parser(s) |
| --- | --- |
| [Lighthouse](frameworks/frontend/lighthouse/) | `lighthouse` |

### Unit-test runners (as timing source)

| Framework | Parser(s) |
| --- | --- |
| [mocha (--reporter json)](frameworks/unit-or-qa/mocha/) | `mocha_json` |
| [Jest (jest-junit)](frameworks/unit-or-qa/junit-jest/) | `junit_standard`, `junit_jest_text` |
| [go test (gotestsum)](frameworks/unit-or-qa/junit-go/) | `junit_go`, `junit_go_text` |
| [JUnit 5 / Maven Surefire](frameworks/unit-or-qa/junit-vanilla/) | `junit_standard` |
| [dotnet test (TRX)](frameworks/unit-or-qa/dotnet-test/) | `dotnet_test_trx` |
| [CTest (--output-junit)](frameworks/unit-or-qa/ctest/) | `junit_standard`, `ctest_text` |
| [Playwright](frameworks/unit-or-qa/playwright/) | `playwright_json` |

### Generic / escape hatches

| Framework | Parser(s) |
| --- | --- |
| [hyperfine](frameworks/generic/hyperfine/) | `hyperfine_json`, `hyperfine_csv`, `hyperfine_text` |
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

To iterate on a parser without round-tripping through GitHub CI,
run the workflow locally via [`nektos/act`](https://github.com/nektos/act).
See [`docs/act.md`](docs/act.md) for the install, image selection,
and full invocation recipe.



## More Documentation

- **Design:** [`docs/design.md`](docs/design.md) — architecture, data model,
  parser contract.
- **Parser targets:** [`docs/parser-targets.md`](docs/parser-targets.md) —
  what's in scope, what's shipped, what's long-tailed.
- **Canonical sample benchmark:** [`docs/sample-benchmark.md`](docs/sample-benchmark.md) —
  the four fixed tests every framework implements.
- **Workflow conventions:** [`docs/workflow-conventions.md`](docs/workflow-conventions.md) —
  CI conventions for the corpus.
- **Running workflows locally:** [`docs/act.md`](docs/act.md) —
  `nektos/act` install, image selection, running a single workflow,
  simulating `schedule` triggers, limitations, and secrets handling.


