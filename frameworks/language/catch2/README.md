# catch2

[Catch2](https://github.com/catchorg/Catch2) is a C++ test framework
whose v3 series ships a first-class micro-benchmarking mode via the
`BENCHMARK(...)` macro. It is a common choice for C++ projects that
already use Catch2 for unit testing and want to add a few benchmark
cases without pulling in a second framework.

## Links

- **Sample benchmark** — [`benchmarks.cc`](benchmarks.cc),
  built by [`CMakeLists.txt`](CMakeLists.txt) and orchestrated by
  [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/catch2.yml`](../../../.github/workflows/catch2.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/catch2.yml>
- **Parser** — [`src/benchzoo/parsers/catch2.py`](../../../src/benchzoo/parsers/catch2.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_catch2.py`](../../../tests/parsers/test_catch2.py) *(not yet written)*

Catch2's `--reporter junit` output is handled by the shared
`junit_standard` parser — see [`docs/parser-targets.md`](../../../docs/parser-targets.md)
section 6. Note that Catch2's benchmark statistics do **not** appear
in junit output; only assertion-based test cases do. Use `catch2_xml`
against the native XML reporter to capture benchmark timings.

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
Catch2 v3 idiom. The four tests live in
[`benchmarks.cc`](benchmarks.cc) as four `TEST_CASE` blocks, each
containing one `BENCHMARK("benchmarkN")` with an explicit name so the
reported entry maps directly to the benchzoo
`attributes["test_name"]`.

- **Test 1** (sleep 2.15 s) — `std::this_thread::sleep_for(2150 ms)`
  inside a `BENCHMARK("benchmark1") { ... return 0; };` block. Catch2
  auto-calibrates its benchmark runs: by default it collects 100
  samples, each of one or more iterations. For a deterministic 2.15 s
  sleep the calibrator settles on one iteration per sample, and the
  100 samples take ~215 s of wall time total. The **per-iteration
  mean** reported in the output is the ~2.15 s we asked for — parsers
  must read the mean / low / high, not the aggregate run time. This
  is the same caveat as Google Benchmark's auto-iterations: a
  benchmark framework that measures will always multiply the
  measurement.
- **Test 2** (tight CPU loop) — a plain `for (int i = 0; i < 1000;
  ++i)` loop with a hand-rolled `do_not_optimize` helper applied to
  the loop counter each iteration. Catch2 does not ship a named
  `DoNotOptimize` helper equivalent to Google Benchmark's
  `benchmark::DoNotOptimize(...)`, so we assign the value into a
  `volatile` sink — the compiler is forbidden from eliding stores to
  a volatile-qualified object, which forces the loop to execute. We
  deliberately avoid C++26's `std::hint::black_box` because it is
  not yet widely available on the GCC/Clang that ship with
  ubuntu-latest.
- **Test 3** (write 1.4 MB to /dev/null) — a 1,400,000-byte
  `std::vector<char>` is filled once (outside the `BENCHMARK` lambda)
  via a simple xorshift so we don't pull in any dependency beyond the
  standard library. Each iteration opens an
  `std::ofstream("/dev/null", std::ios::binary | std::ios::out)`,
  writes the buffer, and a `do_not_optimize` call on the stream's
  `rdbuf()` pointer keeps the compiler from proving the whole write
  is dead.
- **Test 4** (monthly change point) — uses
  `std::chrono::system_clock::now()` + `gmtime_r` to read the UTC
  month, computes the sleep duration as
  `2150 + ((month mod 3) - 1) * 1000` milliseconds, and sleeps for
  that many ms. UTC (`gmtime_r`, not `localtime_r`) is critical:
  runners in different timezones must produce the same month value
  on the same calendar day. Same sample-count caveat as test 1.

The build lives in [`CMakeLists.txt`](CMakeLists.txt), which uses
CMake's `FetchContent` to download and build Catch2 at configure
time, pinned to a specific tag (currently `v3.7.1`) so the captured
fixture is a function of a known upstream version. Linking against
`Catch2::Catch2WithMain` pulls in Catch2's own `main()`; the v2-era
`#define CATCH_CONFIG_ENABLE_BENCHMARKING` is not needed in v3 — the
`BENCHMARK` macros are first-class.

The orchestration lives in [`run.sh`](run.sh): `cmake -S . -B build
-DCMAKE_BUILD_TYPE=Release`, `cmake --build build`, then four runs of
`./build/sample_benchmark`, one per output format (console text, XML,
JUnit XML, and JSON — the JSON run is best-effort since it depends on
the Catch2 version). `Release` is non-negotiable — a Debug build
would make test 2 report wildly inflated, meaningless numbers.

## Running locally

```bash
act push -W .github/workflows/catch2.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/catch2-output/` containing
`output.txt`, `output.xml`, `output.junit.xml`, and (on Catch2 v3.4+)
`output.json`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with a modern CMake and a C++17 compiler installed
locally, you can bypass `act` entirely and just run `./run.sh` from
this directory. The first run will take a minute or two to fetch and
build Catch2; subsequent runs reuse the `build/` directory.

## Parser notes

Catch2 v3 supports several reporters for benchmark output. All of
them are captured by `run.sh`:

**Console text** (default, `--reporter console`) is a pretty
human-readable table. For benchmark runs Catch2 prints a block per
benchmark looking roughly like:

```
benchmark name                          samples    iterations       est run time
                                        mean       low mean         high mean
                                        std dev    low std dev      high std dev
-------------------------------------------------------------------------------
benchmark1                              100         1               3m 35s
                                        2.15 s      2.15 s          2.15 s
                                        1.2 ms      0.9 ms          1.8 ms
```

Columns: `samples` (how many samples were collected), `iterations`
(how many times the benchmark body ran per sample), `est run time`
(estimated wall time the whole block took), `mean` (per-iteration
mean with a low / high confidence interval), and `std dev` (standard
deviation with its own low / high interval). The text format is
parseable but whitespace-sensitive; structured formats below are
preferred.

**XML** (`--reporter xml`) is Catch2's native structured format. It
wraps each benchmark in a `<BenchmarkResults name="..."
samples="..." resamples="..." iterations="..." clockResolution="..."
estimatedDuration="...">` element containing `<mean value="..."
lowerBound="..." upperBound="..." ci="..." />` and
`<standardDeviation ...>` children, with wall-clock values in
nanoseconds. This is the richest of the machine-readable formats and
is the recommended input for the primary Catch2 parser.

**JUnit XML** (`--reporter junit`) emits standard JUnit `<testsuite>`
/ `<testcase>` shape, consumed by the shared `junit_standard` parser.
Benchmark-mode statistics do **not** appear in this format — only
assertion-based test cases — so it's useful for tracking test-suite
wall time, not benchmark throughput. Use the native `--reporter xml`
(and `catch2_xml`) for benchmark timings.

**JSON** (`--reporter json`, Catch2 v3.4+) is a newer reporter whose
format is still evolving upstream. We capture it when available
(`run.sh` tolerates failure on older Catch2 versions) and will lock
in a parser once it stabilizes.

### Ground-truth assertions

The canonical ground-truth values from
[`docs/sample-benchmark.md`](../../../docs/sample-benchmark.md#ground-truth-values-and-why-they-matter)
apply here directly. Test 1's reported `mean` will be ~2.15 s; the
corresponding assertion is `2.0 < mean < 2.3` (in seconds, after
converting from Catch2's nanosecond XML values). Test 2's `mean`
will be small but non-zero (sub-microsecond per iteration of a
1000-count empty loop, reported in ns). Test 3's `mean` will be a
few hundred µs to ~1 ms.

### Fork reference

The predecessor TypeScript project at
[`nyrkio/change-detection`][fork] shipped a Catch2 parser. It is
reference-only — benchzoo's parser is written from scratch against a
real captured fixture — but the fork's parser is a useful cross-check
for XML field interpretation and for the per-producer JUnit
extensions Catch2 emits.

[fork]: https://github.com/nyrkio/change-detection
