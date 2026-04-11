# Parser targets

What benchzoo aims to ingest. Curated and opinionated, **not exhaustive**.
Any source of per-test or per-operation timing is fair game; the lists below
are prioritized by how much real-world traffic they're likely to bring.

Each section maps to a directory under `frameworks/` in the repo, where the
sample benchmark implementation, captured fixture outputs, and (eventually)
producer-specific parser code for each framework will live. Each framework
also gets a corresponding `.github/workflows/<framework>.yml` GitHub Actions
workflow that runs the sample benchmark on every push/PR and uploads the
native output as an artifact — see
[`workflow-conventions.md`](workflow-conventions.md) for the convention.

Tools tagged `[fork]` already had a parser in the predecessor TypeScript
project at `nyrkio/change-detection`. The fork is reference-only — these
tags exist to flag where stale fixtures or design ideas can be cribbed, not
to imply we'll port the code.

## 1. Native benchmark frameworks (per-language) → `frameworks/language/`

These are dedicated benchmark libraries inside language ecosystems. They
emit purpose-built output, usually with statistics (mean, stddev, p99,
etc.) already computed. Highest signal per unit of parser effort.

| Language    | Framework                       | Notes                                                                                         |
| ----------- | ------------------------------- | --------------------------------------------------------------------------------------------- |
| Rust        | **criterion** `[fork]`          | De-facto Rust benchmarking standard. JSON + text output.                                      |
| Rust        | `cargo bench` (libtest) `[fork]`| Older, still used. Plain text output.                                                         |
| Java/JVM    | **JMH** `[fork]`                | Effectively the only credible micro-benchmark tool on the JVM. JSON, text, CSV outputs.       |
| C++         | **Google Benchmark** `[fork]`   | JSON output is well-defined.                                                                  |
| C++         | Catch2 (benchmark mode) `[fork]`| Both v2 and v3; outputs differ.                                                               |
| C# / .NET   | **BenchmarkDotNet** `[fork]`    | Standard for .NET. Emits JSON.                                                                |
| Go          | `go test -bench` `[fork]`       | Stdlib `testing.B`. Universally used. `benchstat` is the usual aggregator.                    |
| Python      | **pytest-benchmark** `[fork]`   | The most popular Python benchmarking tool by far. JSON output.                                |
| Python      | asv (airspeed velocity)         | Used by NumPy, SciPy, scikit-learn. Slightly more complex (history-aware) but high-impact.    |
| JavaScript  | benchmark.js `[fork]`           | Old but still used.                                                                           |
| JavaScript  | tinybench, mitata               | Newer alternatives gaining ground.                                                            |
| JS / TS     | **vitest bench** (`vitest bench`)| Vitest's built-in benchmark mode is becoming the modern default in JS land.                  |
| Julia       | BenchmarkTools.jl `[fork]`      | JSON output well-defined.                                                                     |
| Lua         | benchmarkluau `[fork]`          | Niche (Roblox's Luau).                                                                        |
| Ruby        | benchmark-ips                   | The standard.                                                                                 |
| Swift       | XCTest `measure`, swift-benchmark| Apple's built-in plus a third-party option.                                                  |
| Haskell     | criterion (Haskell)             | Confusingly same name as the Rust one; different format.                                      |
| PHP         | PHPBench                        | The standard for PHP.                                                                         |
| Scala       | sbt-jmh, ScalaMeter             | sbt-jmh delegates to JMH; ScalaMeter is older.                                                |

## 2. Load / API testing tools → `frameworks/loadtest/`

These send traffic at a service and measure response times, throughput,
percentiles. Output formats vary widely; some emit JSON natively, some only
have text reports.

**Heavy hitters:**

- **k6** (Grafana) — JSON output is well-structured. Widely adopted in
  cloud-native shops.
- **JMeter** — old guard, still ubiquitous in enterprise. CSV and XML
  output; the CSV is the easier ingest path.
- **Gatling** — Scala-based, popular for serious load tests. JSON
  ("simulation log") and HTML reports.
- **Locust** (Python) — growing share. CSV stats files are easy to parse.
- **wrk / wrk2** — text output, parseable; the de-facto baseline for HTTP
  benchmarks in research papers.

**Smaller but worth supporting:**

- **vegeta** (Go) — JSON output, very structured.
- **hey** (Go), **bombardier** (Go), **oha** (Rust), **autocannon** (Node),
  **artillery** (Node), **apib**, **siege**, **ab** (Apache Bench).

## 3. Database benchmarks → `frameworks/database/`

A whole ecosystem of its own. These tools target databases specifically —
relational, NoSQL, time-series, analytical — and have their own conventions
for output. Formats range from "stdout text with summary lines" to
"CSV/JSON dumps with per-query breakdown" to "log files of every operation."

Important enough for Nyrkiö's target market that this category may end up
the single biggest source of real-world fixtures.

**Multi-purpose / general:**

- **sysbench** — old, classic, ubiquitous. Multi-purpose: `cpu`, `memory`,
  `fileio`, `mutex`, `oltp_read_only` / `oltp_read_write` /
  `oltp_write_only`. Lua-scriptable for custom workloads. Text output with
  throughput and latency percentiles. **Day-1 priority.**
- **pgbench** — Postgres's built-in benchmark (TPC-B-like by default; also
  supports custom scripts). Text output with TPS and latency stats.
  Universal in Postgres land. **Day-1 priority.**
- **HammerDB** — popular cross-database tool. GUI-driven but also CLI.
  Implements TPC-C and TPC-H against many DBs.
- **YCSB** (Yahoo Cloud Serving Benchmark) — the standard for NoSQL and
  distributed databases. Text output with throughput and latency
  percentiles. Has many forks (go-ycsb from PingCAP, etc.).
- **OLTPBench / BenchBase** (CMU academic) — multi-DB benchmark framework.
  Supports many workloads against many DBs.

**TPC-C implementations specifically:**

- **HammerDB** (above)
- **BenchmarkSQL**
- **Percona `tpcc-mysql`**
- **sysbench `oltp_*`** (TPC-C-like, not strictly compliant)
- **go-tpc** (PingCAP / TiDB)
- **py-tpcc**
- **DBT-2** (open-source TPC-C from OSDL)

**Analytical (OLAP) benchmarks:**

- **ClickBench** (ClickHouse Inc.) — fast-moving standard for analytical
  database comparison. JSON/markdown result format we can ingest directly.
  **Day-1 priority.**
- **TPC-H, TPC-DS** — classic analytical benchmarks; many implementations.
- **Star Schema Benchmark (SSB)**
- **HiBench** (Spark/Hadoop)

**Workload-specific:**

- **Mark Callaghan's insert benchmark** — long-running write-intensive
  benchmark used for years to compare MySQL/MyRocks/Postgres/etc. Outputs
  are typically text logs and spreadsheets. Niche but high-value if we want
  to ingest his published results directly.
- **Linkbench** (Facebook) — graph/social workload.
- **tsbs** (Time Series Benchmark Suite, TimescaleDB) — time-series
  databases.
- **TPCx-IoT** — IoT workload.

**Database-vendor-specific:**

- **cassandra-stress** (Cassandra)
- **redis-benchmark** (Redis)
- **memtier_benchmark** (Redis Labs) — Redis/memcached
- **mongo-perf** (MongoDB)

**v0 priorities for this category:** **sysbench, pgbench, ClickBench.**
These three between them cover OLTP relational, Postgres-native, and OLAP —
a broad first sweep with manageable parser effort.

## 4. ML / AI benchmarks → `frameworks/ml-ai/`

A category of its own, and increasingly important. Outputs vary widely —
from heavily-structured JSON (MLPerf) to ad-hoc text logs (vendor inference
benchmarks). Four sub-categories worth distinguishing:

**Standardized industry benchmarks:**

- **MLPerf** (MLCommons) — the big standardized suite, with separate
  Training, Inference, HPC, and Tiny tracks. Each emits structured JSON
  results plus extensive logs. The de-facto cross-vendor standard.
  **Day-1 priority** for this category.
- **TPCx-AI** — TPC's AI benchmark. Less common than MLPerf but worth
  knowing about.

**LLM-specific inference benchmarks:**

The hot growth area. Most are scripts rather than frameworks; outputs are
usually CSV or JSON with latency and throughput stats.

- **vLLM benchmark scripts** — `benchmark_serving.py`,
  `benchmark_throughput.py`. De facto standard for comparing LLM serving
  runtimes.
- **TensorRT-LLM benchmarks** — Nvidia's serving benchmark.
- **lm-evaluation-harness** (EleutherAI) — primarily a model-quality
  evaluation tool, but records per-task timing.
- **HELM** (Stanford) — Holistic Evaluation of Language Models. Quality +
  timing in the same output.
- **llama.cpp benchmark**, **MLC-LLM benchmarks**, etc.

**Operator / kernel-level benchmarks:**

- **DeepBench** (Baidu) — primitive operations (matmul, conv, etc.). Older
  but still cited.
- **PerfZero** — TensorFlow's perf benchmark framework.
- **NVIDIA `nsys` / `ncu`** profiler outputs — not strictly benchmarks but
  contain rich per-kernel timing data.
- **Microbenchmarks shipped with PyTorch / JAX / TensorFlow** —
  inconsistent formats, mostly text.

**Training perf telemetry:**

- **Weights & Biases (wandb)** export format — JSON exports of training
  runs with per-step times. Not a benchmark per se but a common source of
  per-step timing in production model training.
- **TensorBoard scalars** — same idea, different format.

**v0 priorities for this category:** **MLPerf Inference** (most
standardized output) and **vLLM benchmark CSV** (most-used in current LLM
serving practice). HELM and lm-evaluation-harness come later as user
demand shows up.

## 5. Frontend / web performance measurement → `frameworks/frontend/`

Tools whose primary purpose is measuring the performance of web pages,
browser sessions, or end-to-end user flows. (Browser-based *test runners*
like Playwright and Cypress live in section 6, not here — they're test
runners first, even though they happen to use a browser.)

- **Lighthouse / Lighthouse CI** — Google's web performance auditor. JSON
  output with web vitals (LCP, FID, CLS, TTI, etc.). The highest-value
  frontend target.
- **WebPageTest** — JSON output; widely used by perf engineers.
- **sitespeed.io** — JSON output with rich metrics.

## 6. Unit test / QA frameworks (per-test duration) → `frameworks/unit-or-qa/`

Most unit test runners — and end-to-end / QA test runners — record
per-test duration in machine-readable output, even though they're not
"benchmarks." If test names are stable, that's a perfectly usable
performance time series.

**Per-producer parsers** — see the *Resolved questions* section below.
Each producer that emits junit XML or its own native format gets its own
parser file (`junit_pytest`, `junit_jest`, `junit_dotnet`, `junit_go`,
`junit_catch2`, `junit_playwright`, ...) so producer-specific extensions
like pytest-benchmark's `<properties>` can be extracted properly. A
separate `junit_vanilla` (or similarly named) parser handles raw Java
JUnit / Maven Surefire and anything else we don't have a producer-specific
parser for.

**Native JSON / structured outputs (preferred where they exist):**

| Runner          | Native format                                  |
| --------------- | ---------------------------------------------- |
| pytest          | `--durations=N` text, `pytest-json-report`, `--junitxml` |
| jest            | `--json` reporter, `jest-junit`                |
| vitest          | `--reporter=json`, `--reporter=junit`          |
| go test         | `-json` (line-delimited; very clean)           |
| mocha           | `--reporter json`, `mocha-junit-reporter`      |
| rspec           | `--format json`, `--profile`                   |
| PHPUnit         | `--log-junit`, `--testdox`                     |
| dotnet test     | TRX, JUnit                                     |
| CTest           | XML (`--output-junit`)                         |
| cargo test      | libtest output; JUnit via `cargo-nextest`      |
| JUnit (Java)    | JUnit XML (the original)                       |
| QtTest          | XML output                                     |
| TAP             | Test Anything Protocol with timing extensions  |
| **Playwright**  | `--reporter=json`, `--reporter=junit`, `--reporter=html` |
| **Cypress**     | `mocha-junit-reporter`, JSON via custom reporters |
| **Puppeteer**   | scripted — output depends on the test runner driving it |

## 7. Generic / escape hatches → `frameworks/generic/`

The catch-all category for things that aren't tied to a specific named
framework. Two sub-buckets: CLI / OS-level timing tools, and (stretch)
structured log file formats. Both share the spirit of "ingest these when
no proper framework applies."

### 7a. CLI / OS-level timing tools

Single-shot programs that measure wall-clock or resource cost of a
subprocess. Useful when there's no framework, just "time this command."

- **Unix `time`** (bash builtin and `/usr/bin/time`) `[fork]` — already
  supported in the fork (the parser the user contributed themselves). High
  priority — it's the lowest common denominator.
- **GNU `time -v` / `-f`** — extended format with maxrss, cpu%, page
  faults. Worth parsing in addition to plain `time`.
- **hyperfine** — modern shell benchmark tool. Emits JSON. **Day-1
  priority** — specifically built for benchmarking commands and
  increasingly the default modern choice over `time`.
- **multitime** — older alternative to hyperfine; runs a command N times
  and reports stats.
- **`perf stat`** — Linux perf counter output. CSV and text formats.
- **Custom CSV / JSON shapes** `[fork]` — the fork has
  `customBiggerIsBetter` / `customSmallerIsBetter` JSON formats and a
  generic CSV parser. Important escape hatches: if a user has a tool we
  don't natively support, they convert to one of these.

### 7b. Log files with timestamps (stretch)

If a log file contains structured events with timestamps, intervals
between event pairs (start/end) are usable as a time series. Stretch goal —
defer until the structured-format parsers are in good shape.

- **JSON Lines** (jsonl) — common in modern services, often with a
  `timestamp` field.
- **logfmt** — `key=value` pairs, used by Heroku, Grafana Loki, etc.
- **OpenTelemetry traces / spans** — explicit start/end times, structured.
  Higher payoff but more complex parsing (protobuf or OTLP JSON).
- **Plain timestamped logs** — `2024-01-01T12:00:00Z some event`.
  Heuristic parsing of common formats (ISO 8601, syslog, common log
  format).

---

## Suggested v0 set (highest coverage per parser)

If we want to maximize real-world coverage with the smallest parser
surface, the priority list is roughly:

1. **junitxml** — covers a huge slice of unit testing in one parser.
2. **hyperfine** — modern, JSON, popular, low-effort.
3. **Unix `time`** (both bash builtin and `/usr/bin/time -v`) — universal
   escape hatch.
4. **sysbench** — DB OLTP heavyweight; also covers cpu/memory/fileio.
5. **pgbench** — Postgres-native, ubiquitous in PG land.
6. **ClickBench** — modern OLAP standard.
7. **pytest-benchmark** — Python heavyweight.
8. **criterion (Rust)** — Rust heavyweight.
9. **JMH** — JVM heavyweight.
10. **Google Benchmark** — C++ heavyweight.
11. **BenchmarkDotNet** — .NET heavyweight.
12. **`go test -bench`** — Go heavyweight.
13. **k6** — load-testing heavyweight.
14. **Lighthouse** — frontend heavyweight.
15. **MLPerf Inference** — ML/AI heavyweight; structured JSON.
16. **customBiggerIsBetter / customSmallerIsBetter / generic CSV** —
    "I have my own tool" escape hatches.

That's 16 parsers covering an estimated 80% of the realistic incoming
formats. The rest of the catalog above is the long tail.

---

## Open questions

(none currently)

## Resolved questions

- **Do we record pass/fail for tests/benchmarks?** *Yes, record it; no, do
  not filter on it.* Failed runs flow through with a `passed: false` flag;
  downstream consumers decide what to do with the flag. See *Library
  boundaries* in [`docs/design.md`](design.md).
- **Do we support non-GitHub CIs (GitLab, Buildkite, CircleCI)?**
  *Parser layer is CI-agnostic by construction.* Parsers take
  `bytes`/`str` and return `list[dict]`; they never know or care where
  the input came from. CI integration lives in downstream consumers,
  not in benchzoo, so supporting any new CI is purely an ingest-layer
  change in the consuming project — not a benchzoo change.
- **Junit XML — single parser or one per producer?** *Separate
  per-producer parsers, clearly distinct.* Each producer that emits junit
  XML gets its own parser file (`junit_pytest`, `junit_jest`,
  `junit_dotnet`, `junit_go`, `junit_catch2`, ...) so producer-specific
  extensions like pytest-benchmark's `<properties>` can be extracted
  properly without hidden auto-detection logic. A separate `junit_vanilla`
  (or similarly named) parser handles raw Java JUnit / Maven Surefire and
  anything else we don't have a producer-specific parser for. The tradeoff
  — more parser files, and the user / config has to indicate which
  producer their output came from — is accepted in exchange for each
  parser doing one thing clearly.
