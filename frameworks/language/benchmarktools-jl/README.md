# BenchmarkTools.jl (Julia)

[BenchmarkTools.jl](https://github.com/JuliaCI/BenchmarkTools.jl) is
Julia's standard micro-benchmark library. It runs each benchmark many
times, collects per-sample wall-clock, GC, memory, and allocation
counts, and exposes a `BenchmarkTools.save(path, result)` entry point
that serializes a whole `BenchmarkGroup` to JSON in a well-defined,
tagged format.

## Links

- **Sample benchmark** — [`bench.jl`](bench.jl), orchestrated by
  [`run.sh`](run.sh) (see also [`Project.toml`](Project.toml))
- **Workflow** — [`.github/workflows/benchmarktools-jl.yml`](../../../.github/workflows/benchmarktools-jl.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/benchmarktools-jl.yml>
- **Parser** — [`src/benchzoo/parsers/benchmarktools_jl.py`](../../../src/benchzoo/parsers/benchmarktools_jl.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_benchmarktools_jl.py`](../../../tests/parsers/test_benchmarktools_jl.py) *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
BenchmarkTools.jl idiom. All four tests are registered as entries in a
single top-level `BenchmarkGroup()`, keyed by the canonical names
`"benchmark1"` .. `"benchmark4"` — those keys are exactly what lands
in the serialized JSON and what the parser keys `test_name` off.

- **Test 1** (sleep 2.15 s) — `@benchmarkable sleep(2.15)` with
  `samples=3 evals=1` to bound total wall time at roughly 3 × 2.15 s ≈
  6.5 s. BenchmarkTools's default auto-tuning would otherwise run
  dozens of samples for no useful signal — the sleep duration is
  deterministic, statistical tightness is not what parser tests care
  about.
- **Test 2** (tight CPU loop) — `sum(1:TEST2_BOUND[])` rather than an
  empty `for i in 1:1000 end`. Julia's compiler will constant-fold
  `sum(1:1000)` to `500500` and will eliminate an empty loop entirely
  — both destroy the measurement. Reading the bound through a `Ref`
  (`TEST2_BOUND[]`) keeps the range out of the compiler's constant
  propagation, and `sum` carries a data dependency on `i` that forces
  the loop body to execute. This is the BenchmarkTools analogue of
  Rust's `std::hint::black_box` or JMH's `Blackhole.consume`.
- **Test 3** (write 1.4 MB to /dev/null) —
  `write(devnull, rand(UInt8, 1_400_000))`. `devnull` is Julia's
  portable bit-bucket IO (/dev/null on Unix, NUL on Windows). The 1.4
  MB buffer is pseudo-random with a fixed `Random.seed!(0)` for
  reproducibility across runs; byte values are immaterial since
  `devnull` discards its input.
- **Test 4** (monthly change point) — month is read once at script
  start via `Dates.month(Dates.now(Dates.UTC))`, the sleep duration is
  computed as `2.15 + ((m mod 3) - 1)`, and the benchmark is
  `@benchmarkable sleep($TEST4_SLEEP)` with `samples=3 evals=1`, same
  wall-time budgeting as test 1. Month is captured at script start
  rather than inside the closure so samples cannot straddle a month
  boundary.

Orchestration lives in [`run.sh`](run.sh): one `Pkg.instantiate()` to
pin BenchmarkTools at the version declared in `Project.toml`, then
`julia --project=. bench.jl` to run the suite and call
`BenchmarkTools.save("output.json", results)`.

## Running locally

```bash
act push -W .github/workflows/benchmarktools-jl.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/benchmarktools-jl-output/output.json`.
See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

With a local Julia toolchain you can alternatively run `./run.sh`
directly. The first invocation downloads BenchmarkTools and compiles
it into Julia's precompile cache (slow); subsequent runs reuse the
cache.

## Parser notes

BenchmarkTools.jl's JSON output comes from
`BenchmarkTools.save(path, result)` and carries **tagged type
information** — it is not a naive dump of Trial fields but a
BenchmarkTools-specific serialization designed to round-trip through
`BenchmarkTools.load(path)`.

### Output file shape

The top-level JSON document is a two-element array:

```
[<metadata>, <payload>]
```

The first element is a small object identifying the BenchmarkTools
version and the schema version the file uses (the exact shape is
`{"Julia": "1.11.x", "BenchmarkTools": "1.5.0"}` under current
versions). The second element is the payload: a nested array whose
structure mirrors the saved Julia object. For a single `BenchmarkGroup`
saved at the top level, the payload is:

```
[
  ["BenchmarkGroup"],
  [
    {
      "tags": [],
      "data": {
        "benchmark1": [["Trial"], { ...trial fields... }],
        "benchmark2": [["Trial"], { ...trial fields... }],
        "benchmark3": [["Trial"], { ...trial fields... }],
        "benchmark4": [["Trial"], { ...trial fields... }]
      }
    }
  ]
]
```

Every tagged Julia type is serialized as a two-element array
`[[<type-name>], <fields>]`. That's the pattern the parser has to
thread through: `[["BenchmarkGroup"], [...]]`,
`[["Trial"], {...}]`, and further down `[["Parameters"], {...}]`. The
type tag is always a single-element array, which is how you
distinguish a tagged type from a naturally-occurring pair.

### Trial fields

Each benchmark's `Trial` object, once you descend through the tag
wrapper, contains:

- `params` — a tagged `Parameters` object holding the configuration
  used for this bench: `seconds`, `samples`, `evals`, `overhead`,
  `gctrial`, `gcsample`, `time_tolerance`, `memory_tolerance`.
- `times` — an array of per-sample wall-clock measurements in
  **nanoseconds** (Float64). Length matches the effective `samples`
  count; for our `samples=3` benches (1 and 4) this array has three
  entries.
- `gctimes` — an array parallel to `times`, per-sample GC time in
  **nanoseconds**.
- `memory` — total bytes allocated per evaluation (integer).
- `allocs` — total number of allocation events per evaluation
  (integer).

### Units

**Times are nanoseconds (Float64 ns) throughout.** BenchmarkTools
stores everything in ns internally and that is exactly what lands in
the JSON. The parser should emit metrics with `unit: "ns"` rather
than converting to seconds; downstream consumers that want seconds can
divide by 1e9 at the edge. Memory is in `bytes`, allocs is a
dimensionless count (emit without a unit, or `unit: ""`).

### Metric mapping

Minimum viable parse: for each `Trial`, compute summary statistics
from the `times` array — BenchmarkTools itself exposes `mean`,
`median`, `minimum`, `maximum`, `std` over trials, but the parser can
recompute them from the raw `times` list without depending on Julia.
Emit (at least):

- `mean` — ns, `lower_is_better`.
- `median` — ns, `lower_is_better`.
- `min` — ns, `lower_is_better`.
- `std` — ns, `lower_is_better`.
- `memory` — bytes, `lower_is_better`.
- `allocs` — count, `lower_is_better`.

`attributes["test_name"]` comes from the key in the `BenchmarkGroup`'s
`data` dict (`"benchmark1"` .. `"benchmark4"`).

### Why `samples=3` on tests 1 and 4

BenchmarkTools's default auto-tuner aims for ~5 s of wall-clock
sampling per bench. A bench whose single iteration is a 2.15 s sleep
would be run roughly twice at defaults, but the auto-tuner would also
spend a fair amount of time in its tuning phase evaluating how many
evals per sample to use — and `evals=1` is not the default, so without
pinning it BenchmarkTools will stack multiple sleeps into one sample
and inflate the effective measurement. Pinning `samples=3 evals=1`
produces exactly three per-sample entries in `times`, each holding the
duration of one `sleep(2.15)` call, and bounds total wall time at ~6.5
s per sleep-heavy bench.

Parsers do not need to know this — it is purely a budget knob. But
anyone looking at `length(trial.times) == 3` for tests 1 and 4 and
wondering why it is not 100 or 1000 should know it was deliberate.

### Pass/fail

BenchmarkTools has no first-class notion of "this benchmark failed."
An exception thrown inside a `@benchmarkable` body aborts that entry
during `run()`, and the failing entry is absent from the saved
`BenchmarkGroup`. For the canonical sample benchmark, treat any
benchmark present in the JSON as `passed: true`. A parser that wants
to detect partial runs can compare the set of keys under `data` to the
expected `{benchmark1..benchmark4}` set, but that is a higher-level
concern — benchzoo's parser contract is still "parse what you see and
surface it."
