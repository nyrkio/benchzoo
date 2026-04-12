# google-benchmark

[Google Benchmark](https://github.com/google/benchmark) is the
de-facto C++ micro-benchmarking library, the C++ counterpart to JMH
(Java) or criterion (Rust). It emits structured JSON results with a
stable, well-documented schema.

## Links

- **Sample benchmark** — [`benchmarks.cc`](benchmarks.cc),
  built by [`CMakeLists.txt`](CMakeLists.txt) and orchestrated by
  [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/google-benchmark.yml`](../../../.github/workflows/google-benchmark.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/google-benchmark.yml>
- **Parser** — [`src/benchzoo/parsers/google_benchmark.py`](../../../src/benchzoo/parsers/google_benchmark.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_google_benchmark.py`](../../../tests/parsers/test_google_benchmark.py) *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
Google Benchmark idiom. The four tests live in
[`benchmarks.cc`](benchmarks.cc) and are registered with explicit
names `benchmark1` .. `benchmark4` via `BENCHMARK(...)->Name("...")`
so the JSON `name` field maps directly to the benchzoo
`attributes["test_name"]`. All four use
`->Unit(benchmark::kMillisecond)` so reported `real_time` / `cpu_time`
come out in milliseconds.

- **Test 1** (sleep 2.15 s) — `std::this_thread::sleep_for(2150 ms)`
  inside the `for (auto _ : state)` loop, registered with
  `->Iterations(1)`. The explicit iteration count matters: by default
  Google Benchmark autoscales iteration counts to reach a minimum
  total wall time of ~0.5 s, which for a deterministic 2.15 s sleep
  would either multiply the sleep or produce misleading per-iteration
  numbers. Pinning to one iteration makes the reported `real_time`
  exactly the 2.15 s we asked for.
- **Test 2** (tight CPU loop) — a plain `for (int i = 0; i < 1000;
  ++i)` loop inside the `State` loop, with
  `benchmark::DoNotOptimize(i)` called on the loop counter. Google
  Benchmark's entire reason for existing is that C++ compilers will
  delete an empty loop whose side effects are unobservable, so we
  *must* use its `DoNotOptimize` helper (the canonical idiom) to keep
  the loop from being folded away at `-O2`/`-O3`. The sister helper
  `benchmark::ClobberMemory()` is also available but not needed here
  — nothing writes to memory.
- **Test 3** (write 1.4 MB to /dev/null) — a 1,400,000-byte
  `std::vector<char>` is filled once (outside the `State` loop) via a
  simple xorshift so we don't pull in any dependency beyond the
  standard library. Each iteration opens an
  `std::ofstream("/dev/null", std::ios::binary | std::ios::out)`,
  writes the buffer, and wraps the stream in `DoNotOptimize` so the
  compiler can't prove the write is dead. No `->Iterations(1)` here;
  the library is free to run this however many times it needs to hit
  its minimum measurement window.
- **Test 4** (monthly change point) — uses
  `std::chrono::system_clock::now()` + `gmtime_r` to read the UTC
  month, computes the sleep duration as
  `2150 + ((month mod 3) - 1) * 1000` milliseconds, and sleeps for
  that many ms. Registered with `->Iterations(1)`, same rationale as
  test 1. UTC (`gmtime_r`, not `localtime_r`) is critical: runners in
  different timezones must produce the same month value on the same
  calendar day.

The build lives in [`CMakeLists.txt`](CMakeLists.txt), which uses
CMake's `FetchContent` to download and build google/benchmark at
configure time, pinned to a specific tag (currently `v1.9.1`) so the
captured fixture is a function of a known upstream version. Google
Benchmark's own test suite and GoogleTest dependency are disabled via
`BENCHMARK_ENABLE_TESTING OFF` / `BENCHMARK_ENABLE_GTEST_TESTS OFF` —
we only need the library and its `benchmark_main` entry point. The
resulting executable is `./build/sample_benchmark`.

The orchestration lives in [`run.sh`](run.sh): `cmake -S . -B build
-DCMAKE_BUILD_TYPE=Release`, `cmake --build build`, then two runs of
`./build/sample_benchmark` — one capturing JSON to file and console
text to stdout (via `tee output.txt`), the second capturing CSV to
file. `Release` is non-negotiable — a Debug build would make test 2
report wildly inflated, meaningless numbers.

## Running locally

```bash
act push -W .github/workflows/google-benchmark.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/google-benchmark-output/` containing
`output.json`, `output.csv`, and `output.txt`.
See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with a modern CMake and a C++17 compiler installed
locally, you can bypass `act` entirely and just run `./run.sh` from
this directory. The first run will take a minute or two to fetch and
build google/benchmark; subsequent runs reuse the `build/` directory.

## Parser notes

Google Benchmark supports three output formats: JSON, CSV, and console
text. All three are captured by `run.sh` and uploaded as workflow
artifacts (`output.json`, `output.csv`, `output.txt`).

**JSON** (`--benchmark_out_format=json`) is the richest and preferred
format. It includes full host context (CPU model, caches, num_cpus),
library metadata, and per-benchmark entries with all available fields.
Parsers should use JSON when available.

**CSV** (`--benchmark_out_format=csv`) is a flat table with headers:
`name,iterations,real_time,cpu_time,time_unit,bytes_per_second,items_per_second,label,error_occurred,error_message`.
It lacks the `context` block (no host info) but is convenient for CI
pipelines that ingest tabular data or feed results into spreadsheets.

**Console text** (`--benchmark_format=console` on stdout) is the
familiar human-readable table with dashed separator lines. It is the
least structured of the three and serves mainly as a fallback when
neither JSON nor CSV is available — for example, when someone runs a
benchmark interactively and only has terminal output.

### JSON schema detail

Google Benchmark's JSON schema is stable and well-defined. At the top
level the JSON has two keys:

- `context` — host info (CPU model, caches, mhz, `num_cpus`), library
  build type, and a wall-clock `date` field. The parser reads
  `num_cpus` / CPU info only if it wants to stash it in `extra_info`.
- `benchmarks` — an array of per-benchmark result entries, one per
  registered `BENCHMARK(...)` that actually ran.

Each entry in `benchmarks[]` carries:

| Field                         | Meaning                                                                                      |
| ----------------------------- | -------------------------------------------------------------------------------------------- |
| `name`                        | The registered name. We set this to `"benchmark1"` .. `"benchmark4"` via `->Name(...)`.      |
| `run_name`                    | The same string for non-parameterized benchmarks; differs for `->Arg()` / `->Range()` cases. |
| `run_type`                    | `"iteration"` for normal runs, `"aggregate"` for `Repetitions`-produced summary rows.        |
| `iterations`                  | How many times the inner `for (auto _ : state)` loop ran.                                    |
| `real_time`                   | Wall time per iteration, in the unit named by `time_unit`.                                   |
| `cpu_time`                    | CPU time per iteration, in the unit named by `time_unit`.                                    |
| `time_unit`                   | `"ns"`, `"us"`, `"ms"`, or `"s"`. We set `kMillisecond` so it should be `"ms"`.              |
| `family_index`                | Integer index across the registered benchmark list.                                          |
| `per_family_instance_index`   | Integer index within a parameterized family.                                                 |

### What the parser should emit

For each entry in `benchmarks[]`:

- `attributes["test_name"]` = `name` (or `run_name` — they're the
  same for our non-parameterized case).
- `metrics` = two entries:
  - `{"name": "real_time", "unit": <time_unit>, "value": <real_time>,
    "direction": "lower_is_better"}`
  - `{"name": "cpu_time", "unit": <time_unit>, "value": <cpu_time>,
    "direction": "lower_is_better"}`
- `extra_info` may carry `iterations`, `family_index`,
  `per_family_instance_index`, and host info cribbed from `context`.
  None of these are required.
- `passed` defaults to `true`. Google Benchmark surfaces a failed
  benchmark by setting `"error_occurred": true` and `"error_message":
  "..."` on the entry; if those are present, set `passed: false`.

### Timestamp handling

`context.date` in the output is a wall-clock timestamp (e.g.
`"2025-01-15 10:23:45"`). **Parsers must not use it for the Nyrkiö
`timestamp` field** — per
[`docs/design.md`](../../../docs/design.md#field-semantics), the
`timestamp` field is git-derived (the committer timestamp of the
merge commit that produced the measurement), not benchmark run time.
Parsers always set `timestamp: 0` and let the ingest layer fill in
the real value from commit metadata.

If the parser wants to preserve `context.date` for reference — which
is a fine thing to do — it belongs in `extra_info`, e.g.
`extra_info["benchmark_date"] = context["date"]`. This is the same
pattern the design doc calls out for pytest-benchmark's
`machine_info.machine_time`, JMH's results date, and hyperfine's
start time.

### Ground-truth assertions

The canonical ground-truth values from
[`docs/sample-benchmark.md`](../../../docs/sample-benchmark.md#ground-truth-values-and-why-they-matter)
apply here directly. Because we set `->Unit(benchmark::kMillisecond)`
the parser sees test 1's `real_time` as roughly `2150.0` with
`time_unit` `"ms"`; the corresponding assertion is `2000 < real_time
< 2300` for test 1. Test 2's `real_time` will be small but not zero
(sub-millisecond, reported in ms — so a fraction). Test 3's
`real_time` will be a few milliseconds.

### Fork reference

The predecessor TypeScript project at
[`nyrkio/change-detection`][fork] shipped a google-benchmark parser
of its own. It is reference-only — benchzoo's parser is written
from scratch against a real captured fixture — but the fork's parser
is a useful cross-check for field interpretation and edge cases.

[fork]: https://github.com/nyrkio/change-detection
