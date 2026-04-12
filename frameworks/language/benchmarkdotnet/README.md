# benchmarkdotnet

[BenchmarkDotNet](https://benchmarkdotnet.org/) is the de-facto standard
micro-benchmarking library for .NET. It compiles each benchmarked method
into a purpose-built host process, runs a multi-stage pilot / warmup /
measurement loop, and emits statistics (mean, stddev, median,
percentiles, etc.) plus per-iteration raw measurements in JSON, CSV,
Markdown, and HTML.

## Links

- **Sample benchmark** — [`SampleBenchmark.cs`](SampleBenchmark.cs),
  [`Program.cs`](Program.cs),
  [`SampleBenchmark.csproj`](SampleBenchmark.csproj), orchestrated by
  [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/benchmarkdotnet.yml`](../../../.github/workflows/benchmarkdotnet.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/benchmarkdotnet.yml>
- **Parser** — [`src/benchzoo/parsers/benchmarkdotnet.py`](../../../src/benchzoo/parsers/benchmarkdotnet.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_benchmarkdotnet.py`](../../../tests/parsers/test_benchmarkdotnet.py) *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
BenchmarkDotNet idiom:

- **Test 1** (sleep 2.15 s) — `Benchmark1()` calls
  `Thread.Sleep(2150)`. Void return is fine because `Thread.Sleep` is a
  side-effecting syscall that the JIT cannot elide.
- **Test 2** (tight CPU loop) — `Benchmark2()` accumulates
  `0..1000` into `sum` and **returns the accumulator**. BenchmarkDotNet's
  user guide documents that returning a value from a benchmark method
  is the idiomatic way to prevent dead-code elimination — the returned
  value cannot be proven unused, so the JIT keeps the loop body. Without
  this, the JIT would delete the loop and the reported duration would
  collapse to near-zero.
- **Test 3** (write 1.4 MB to /dev/null) — `Benchmark3()` fills a
  `byte[1_400_000]` from a seeded `Random` and writes it to
  `File.OpenWrite("/dev/null")`. `/dev/null` is Unix-only, so this test
  would throw on Windows. The workflow pins `runs-on: ubuntu-latest` to
  match that assumption; macOS would also work in principle but is not
  exercised.
- **Test 4** (monthly change point) — `Benchmark4()` reads
  `DateTime.UtcNow.Month` (UTC is load-bearing — see
  [`docs/sample-benchmark.md`](../../../docs/sample-benchmark.md#formula))
  and sleeps for `2.15 + ((m % 3) - 1)` seconds.

### Job / run-strategy choice

BenchmarkDotNet's default job runs a pilot stage, several warmup
iterations, and many measurement iterations — perfectly reasonable for
nanosecond-scale micro-benchmarks but pathological for a 2.15-second
`Thread.Sleep`: the default job would keep sleeping for minutes on a
single test. The `SampleBenchmark` class uses

```csharp
[SimpleJob(RunStrategy.Monitoring, iterationCount: 3)]
```

`RunStrategy.Monitoring` is the strategy BenchmarkDotNet documents for
long, noisy, real-world measurements where per-invocation overhead is
negligible — it skips the pilot / warmup stages and measures exactly
the iterations requested. `iterationCount: 3` keeps total wall time
reasonable (roughly `3 * (2.15 + ~0 + ~0 + 2.15) s` plus startup) while
still giving `Statistics.Mean` and `Statistics.StandardDeviation` enough
samples to be meaningful. The class is also tagged
`[JsonExporterAttribute.Full]` and `[CsvExporter]` so both the full-json
report and the CSV report are emitted alongside the default outputs.

## Running locally

```bash
act push -W .github/workflows/benchmarkdotnet.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/benchmarkdotnet-output/` containing
`output.json`, `output.csv`, and `output.txt`.
See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with the .NET 8 SDK installed locally, you can bypass
`act` entirely and just run `./run.sh` from this directory. That
produces the same `output.json` but without the GitHub Actions artifact
plumbing.

## Parser notes

BenchmarkDotNet's full JSON report
(`<Type>-report-full.json`, emitted by `JsonExporterAttribute.Full`) has
two top-level sections:

- **`HostEnvironmentInfo`** — machine, OS, runtime, JIT, GC, CPU,
  hardware counters, BenchmarkDotNet version, build configuration.
  Useful context for `extra_info` if the parser wants it, but **none of
  its date / culture fields are eligible for the Nyrkiö `timestamp`**.
  The design doc is emphatic: parsers always set `timestamp: 0` and the
  ingest layer fills in the git-commit timestamp later. Wall-clock run
  time embedded in the output is the wrong semantics. If the parser
  wants to preserve BenchmarkDotNet's own run timestamp for reference,
  it should stash it in `extra_info` (e.g.
  `extra_info["machine_time"]`).

- **`Benchmarks[]`** — one entry per `[Benchmark]`-annotated method.
  Each entry carries, at minimum:
  - `Namespace`, `Type`, `Method`, `FullName` — identity. `Method`
    is the short-form name, e.g. `"Benchmark1"`.
  - `Parameters` — empty string here (we don't parameterize).
  - `Statistics` — a dict of summary numbers: `N`, `Min`, `Lower fence`,
    `Q1`, `Median`, `Mean`, `Q3`, `Upper fence`, `Max`, `StandardError`,
    `StandardDeviation`, `Variance`, `Skewness`, `Kurtosis`,
    confidence intervals, percentiles (`P0`, `P25`, `P50`, `P67`, `P80`,
    `P85`, `P90`, `P95`, `P100`), etc.
  - `Measurements[]` — the raw per-iteration records, each with
    `IterationMode`, `IterationStage`, `LaunchIndex`, `IterationIndex`,
    `Nanoseconds`, `Operations`.
  - `Memory` — GC stats. Only populated when a memory diagnoser is
    attached (we don't attach one, so expect nulls / zeros).

### CSV format

BenchmarkDotNet's CSV report (`<Type>-report.csv`, emitted by the
`[CsvExporter]` attribute) contains columns such as
`Method`, `Job`, `Mean`, `Error`, `StdDev`, `Median`, `Min`, `Max`.
Each row corresponds to one `[Benchmark]`-annotated method. Numeric
values use the same nanosecond unit as the JSON report. The CSV format
gets its own parser module (`benchmarkdotnet_csv.py`), separate from
the JSON parser, following the multi-format capture convention described
in [`docs/design.md`](../../../docs/design.md).

### Console text format

The console text output (`output.txt`, captured by redirecting stdout
during the run) contains BenchmarkDotNet's human-readable summary
table plus diagnostic information (environment info, job settings,
warnings). This is the format most users see when running benchmarks
interactively. It gets its own parser module as well.

### Mapping to Nyrkiö JSON

- `attributes["test_name"]` ← `Benchmarks[i].Method` (short form,
  e.g. `"Benchmark1"`). **Judgment call for the user:** the C#
  convention is PascalCase, but every other framework's canonical sample
  uses lowercase `"benchmark1"` etc. The parser may choose to lowercase
  the method name to keep cross-framework `test_name` values uniform,
  or preserve PascalCase and let downstream queries cope. Flag this
  decision when the parser is written.
- `metrics` — emit `Statistics.Mean` as the headline metric with
  `unit: "ns"` (BenchmarkDotNet reports all `Statistics.*` values in
  nanoseconds internally — the human-readable table scales the unit,
  but the JSON numbers are always ns). Direction is
  `"lower_is_better"`. Also emit `Statistics.Median`,
  `Statistics.StandardDeviation`, `Statistics.Min`, `Statistics.Max` as
  separate metric entries with the same unit / direction. Higher
  percentiles (`P95`, `P99`) are available too if the parser wants
  them.
- `timestamp` — **always `0`.** Do not read `HostEnvironmentInfo`
  timestamps or culture info for this field.
- `passed` — BenchmarkDotNet does not surface per-benchmark pass/fail
  in the JSON; a benchmark that threw at runtime is simply absent from
  `Benchmarks[]`. For now, assume `passed: true` for every entry that
  appears in the file. If we need failure tracking later, it will have
  to come from the text log, not the JSON report.
- `extra_info` — optional. `HostEnvironmentInfo` fields
  (`RuntimeVersion`, `HasRyuJit`, `CpuInfo`, etc.) are good candidates
  if the parser wants to preserve environment context.

### Return-value idiom for test 2

The reason `Benchmark2` returns `int` rather than `void` is
BenchmarkDotNet's documented protection against dead-code elimination:
the JIT cannot prove a returned value is unused, so it keeps the
computation. A `void` variant would see the loop deleted entirely and
report near-zero duration. Parser tests should still happily consume
either shape — this affects the *benchmark implementation*, not the
output format.

### Reference prior art

The fork at [nyrkio/change-detection][fork] had a BenchmarkDotNet parser
in its TypeScript codebase. That code is **reference-only** — benchzoo
does not port or link to it — but it's a useful starting point for
understanding which JSON fields the fork's author considered load-bearing.

[fork]: https://github.com/nyrkio/change-detection
