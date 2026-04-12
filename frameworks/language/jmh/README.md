# jmh

[JMH](https://github.com/openjdk/jmh) (Java Microbenchmark Harness) is
OpenJDK's benchmarking tool for the JVM. It is effectively the only
credible micro-benchmark framework in Java/Kotlin/Scala land, and takes
care of the hard parts of JVM benchmarking — warmup, JIT steady-state,
dead-code elimination via `Blackhole`, forked processes to isolate
compiled code — that a naive `System.nanoTime()` loop gets wrong.

## Links

- **Sample benchmark** —
  [`src/main/java/io/nyrkio/benchzoo/jmh/SampleBenchmark.java`](src/main/java/io/nyrkio/benchzoo/jmh/SampleBenchmark.java),
  built via [`pom.xml`](pom.xml), run via [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/jmh.yml`](../../../.github/workflows/jmh.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/jmh.yml>
- **Parser** — [`src/benchzoo/parsers/jmh.py`](../../../src/benchzoo/parsers/jmh.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_jmh.py`](../../../tests/parsers/test_jmh.py) *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
JMH idiom, as four `@Benchmark` methods on a single `SampleBenchmark`
class:

- **Test 1** (sleep 2.15 s) — `benchmark1()` calls
  `Thread.sleep(2150)` and declares `throws InterruptedException`.
- **Test 2** (tight CPU loop) — `benchmark2(Blackhole blackhole)` runs
  `for (int i = 0; i < 1000; i++) blackhole.consume(i);`.
  `Blackhole.consume` is **mandatory**: without it HotSpot's JIT proves
  the empty loop has no observable side effects and eliminates the
  entire method body, which would turn the benchmark into "measure
  method call overhead" instead of "measure 1000 loop iterations."
  The Blackhole API exists specifically to defeat dead-code elimination
  in JMH benchmarks.
- **Test 3** (write 1.4 MB to /dev/null) — `benchmark3` fills a
  pre-allocated `byte[1_400_000]` buffer via
  `java.util.Random.nextBytes(buf)` (seeded with 42 for deterministic
  payloads) and writes it through a `FileOutputStream("/dev/null")`
  opened in a try-with-resources. The buffer allocation lives in a
  field so it is not part of the measured path; the RNG work and the
  write itself are.
- **Test 4** (monthly change point) — `benchmark4` reads the current
  UTC month via `ZonedDateTime.now(ZoneOffset.UTC).getMonthValue()`,
  computes `2.15 + ((month mod 3) - 1)` and sleeps for that many
  seconds (in milliseconds for `Thread.sleep`).

### Run-time configuration and trade-off

Class-level annotations are:

```java
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Warmup(iterations = 1, time = 1)
@Measurement(iterations = 3, time = 1)
@Fork(1)
```

JMH's `time` on `@Warmup`/`@Measurement` is the **target batch
duration**, not an invocation count: JMH keeps invoking the benchmark
method until ~`time` seconds have elapsed, then treats that as one
iteration. For `benchmark2` (sub-millisecond) this produces millions of
invocations per iteration, which is what you want for statistical
stability. For `benchmark1` and `benchmark4` (multi-second sleeps) the
opposite happens: a single invocation blows past the 1-second target,
so each iteration is one invocation taking ~2.15 s, and 3 iterations
× 1 fork = ~6.5 s per sleep benchmark plus warmup. Total suite wall
time is on the order of a minute on a GitHub-hosted runner.

We considered overriding `@Measurement(iterations = 1)` on the sleep
methods to shave off a few seconds, but kept a uniform 3-iteration
measurement across all four benchmarks. The uniformity makes the
fixture easier to reason about (same `measurementIterations` field
in every JSON entry) and the ground-truth assertion on `benchmark1`'s
mean is slightly more robust with three samples than with one.

### Build & run

`run.sh` invokes `mvn -q package`, which runs the `maven-shade-plugin`
bound to the `package` phase to produce a self-contained
`target/benchmarks.jar` with `org.openjdk.jmh.Main` as its main class
(this follows JMH's archetype convention). It then runs:

```
java -jar target/benchmarks.jar -rf json -rff output.json | tee output.txt
java -jar target/benchmarks.jar -rf csv  -rff output.csv  > /dev/null
```

- `-rf json` / `-rf csv` selects the result format. JMH only writes
  one format per invocation, so `run.sh` invokes the suite twice.
- `-rff output.json` / `-rff output.csv` sets the output file path.
- JMH's rich text output goes to stdout during the first run — we
  capture it to `output.txt` via `tee`. The second (CSV) run's stdout
  is discarded. All three files are uploaded as the `jmh-output`
  artifact.

## Running locally

```bash
act push -W .github/workflows/jmh.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/jmh-output/` (containing
`output.json`, `output.csv`, and `output.txt`). See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with Java 17 and Maven installed locally, you can bypass
`act` entirely and run `bash run.sh` from this directory.

### act gotchas

JMH always forks a subprocess for the measurement JVM (`@Fork(1)`),
which means the `act` container must permit `fork()`/`exec()` of a
child Java process — the `catthehacker/ubuntu:full-latest` image
supports this, but minimal Alpine-based act images may not. If you see
"Failed to fork the JVM" from JMH, that's the container; switch images.
JMH is also memory-hungrier than most benchmarks here (two JVMs: the
host and the forked measurement JVM, each with default heap settings),
so `act` with aggressive Docker memory limits may OOM the forked JVM.

## Parser notes

JMH's JSON result format (selected via `-rf json`) is a top-level JSON
**array**, one entry per `@Benchmark` method that ran. Each entry has:

- **`benchmark`** — fully-qualified name, e.g.
  `io.nyrkio.benchzoo.jmh.SampleBenchmark.benchmark1`. The parser
  should strip the class prefix and use the tail segment
  (`benchmark1`) as `attributes["test_name"]`. This matches how every
  other sample-benchmark fixture names its tests and keeps the
  ground-truth assertions clean (`test_name == "benchmark1"`, not
  `test_name.endswith(".benchmark1")`). If a future caller prefers the
  fully-qualified name, that's a design call; start with the short
  name.
- **`mode`** — one of `"avgt"` (AverageTime), `"thrpt"` (Throughput),
  `"sample"` (SampleTime), `"ss"` (SingleShotTime). Our
  `SampleBenchmark` uses `@BenchmarkMode(Mode.AverageTime)`, so every
  entry in our fixture has `mode == "avgt"`. Parsers should still
  branch on this field in general, because other projects' JMH
  fixtures will have different modes.
- **`threads`**, **`forks`**, **`warmupIterations`**,
  **`measurementIterations`** — numbers describing the JMH config. All
  useful as `extra_info` entries so the fixture is self-describing.
- **`primaryMetric`** — dict with `score`, `scoreError`,
  `scoreConfidence` (a `[low, high]` pair), `scoreUnit` (typically
  `"ms/op"`, `"us/op"`, `"ns/op"` for `avgt`/`sample`/`ss`, or
  `"ops/s"`-flavored for `thrpt`), `scorePercentiles` (for `sample`
  mode), and `rawData` (nested array of per-fork, per-iteration
  scores).
- **`secondaryMetrics`** — dict of named sub-metrics, populated when
  JMH profilers are attached (e.g. `-prof gc` adds
  `·gc.alloc.rate.norm` etc.). Empty for our default run.

Parser mapping suggestions:

- Emit `primaryMetric.score` as the headline metric. Name it
  `"score"` (or `"mean"`, if that reads better against the
  cross-framework corpus) and take the unit verbatim from
  `primaryMetric.scoreUnit`.
- Emit `primaryMetric.scoreError` as a separate metric (`"error"`,
  same unit) or stash it in `extra_info`. Recommendation: separate
  metric, since it's a statistical summary, not a parameter.
- `direction` depends on `mode`:
  - `"avgt"`, `"sample"`, `"ss"` → `"lower_is_better"` (time per op)
  - `"thrpt"` → `"higher_is_better"` (ops per time unit)
- `threads`, `forks`, `warmupIterations`, `measurementIterations`,
  `jvmArgs`, and any other JMH config fields are natural `extra_info`.
- JMH does not have a clean "this benchmark failed" signal in the
  JSON — a crashed benchmark typically produces no entry rather than
  a failed one, so `passed: true` is the default. If a fixture does
  contain an obviously degenerate entry (score NaN, zero iterations),
  the parser can mark it `passed: false`, but don't invent failure
  detection that isn't backed by a real fixture.

### Three fixtures

We capture `output.json`, `output.csv`, and `output.txt`. Each format
gets its own parser module (`jmh_json.py`, `jmh_csv.py`,
`jmh_text.py`).

**JSON** is the primary parser target — stable, typed, trivial to
consume, and the richest of the three: it includes raw per-iteration
data, percentiles, secondary metrics, and full JMH configuration.

**CSV** (`-rf csv`) is a compact tabular format with one row per
benchmark. Columns are
`Benchmark,Mode,Threads,Samples,Score,Score Error (99.9%),Unit`.
It carries the essential per-benchmark summary (score, error, unit,
mode, thread count, sample count) but lacks the raw iteration data,
percentiles, and secondary metrics present in JSON. CSV is commonly
used in CI reporting pipelines where a quick pass/fail or
threshold check is all that's needed.

**Text** is JMH's rich stdout output, captured via `tee`. It is mostly
useful as a cross-check: when iterating on the parser, grepping
`output.txt` for `2.15` is the quickest way to locate test 1's
reported value and verify the corresponding JSON field maps to the
right thing. Treat `output.txt` as a debugging aid.

### Reference fork

The predecessor TypeScript project at
[`nyrkio/change-detection`](https://github.com/nyrkio/change-detection)
shipped a JMH parser. It is **reference-only** for benchzoo (see
[`docs/design.md`](../../../docs/design.md)): crib ideas and field
mappings if useful, but do not port the code. The Python parser is
written against a real captured fixture, not against the TypeScript.
