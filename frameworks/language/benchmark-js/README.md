# benchmark.js

[benchmark.js](https://benchmarkjs.com/) is the classic Node / browser
micro-benchmarking library. It auto-calibrates iterations per sample,
collects multiple samples, and reports per-benchmark statistics
(`hz` ops/sec, `mean` seconds/op, relative margin of error, stddev,
sample count). Old but still widely used — jsPerf ran on it, and the
predecessor TypeScript project at `nyrkio/change-detection` had a
benchmark.js parser (reference-only; we are free to pick a new output
shape here).

## Links

- **Sample benchmark** — [`sample-benchmark.js`](sample-benchmark.js),
  orchestrated by [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/benchmark-js.yml`](../../../.github/workflows/benchmark-js.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/benchmark-js.yml>
- **Parser** — `src/benchzoo/parsers/benchmark_js.py` *(not yet written)*
- **Parser tests** — `tests/parsers/test_benchmark_js.py` *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
benchmark.js idiom. The four tests are wired into a single
`Benchmark.Suite` as `benchmark1` .. `benchmark4`.

### Per-test mapping

- **Test 1** (sleep 2.15 s) — uses benchmark.js's **deferred mode**
  (`defer: true`, `fn: function(deferred) { setTimeout(() =>
  deferred.resolve(), 2150); }`). A synchronous busy-wait would burn
  CPU and, more importantly, benchmark.js would repeat it across many
  samples — the suite would take minutes. Deferred mode lets the event
  loop breathe between samples and gives us a clean wall-time
  measurement. `minSamples: 5` plus `maxTime: 15` keeps the total
  runtime bounded.
- **Test 2** (tight CPU loop) — plain synchronous `fn`: `for (let i =
  0; i < 1000; i++) sum += i;`, with `sum` written to a module-scoped
  sink so V8 cannot elide it as dead code. benchmark.js will run many
  iterations per sample and the reported `mean` will be
  sub-microsecond.
- **Test 3** (write 1.4 MB to /dev/null) — Node has filesystem access,
  so unlike the k6 adaptation we literally
  `fs.writeFileSync('/dev/null', buf)`. The 1,400,000-byte Buffer is
  allocated once outside the timed function (filled with a Knuth
  multiplicative-hash pattern), so the measurement reflects the write,
  not the allocation.
- **Test 4** (monthly change point) — same deferred-mode
  `setTimeout`-resolve pattern as test 1, with the sleep duration
  computed once at suite-build time as `2.15 + ((UTCMonth % 3) - 1)`
  seconds. The chosen month is emitted into the output JSON under the
  top-level `month` key so fixtures are self-describing.

### microtime dependency

`package.json` pulls in `microtime` as a dependency. benchmark.js
auto-detects and uses it when available, giving sub-microsecond timer
resolution on platforms where `process.hrtime` does not already
provide it. On modern Node this is mostly a no-op — `process.hrtime`
is already nanosecond-resolution — but `microtime` is cheap insurance
and matches benchmark.js's historical recommended setup.

## Running locally

```bash
act push -W .github/workflows/benchmark-js.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/benchmark-js-output/output.json`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with Node 20+ installed locally, `bash run.sh` from this
directory runs the suite directly.

## Parser notes

### Not yet written

The Python parser is not yet written. The predecessor TypeScript
project at `nyrkio/change-detection` contained a benchmark.js parser,
but that was keyed to *its* emit format — benchzoo is free to pick a
shape that suits this corpus, and has done so below. The TS parser is
reference-only per the design doc.

### Output format: `output.json`

benchmark.js is a *library*, not a runner; it has no canonical file
output format. `sample-benchmark.js` itself defines the JSON shape
emitted on stdout and `run.sh` redirects it to `output.json`. The
shape:

```json
{
  "framework": "benchmark.js",
  "version": "2.1.4",
  "month": 4,
  "results": [
    {
      "name": "benchmark1",
      "hz": 0.4651,
      "mean": 2.150,
      "rme": 0.12,
      "deviation": 0.001,
      "variance": 0.000001,
      "moe": 0.002,
      "sem": 0.0005,
      "samples": 5,
      "cycles": 1,
      "deferred": true,
      "passed": true
    }
  ]
}
```

Field semantics:

- `name` — benchmark.js's benchmark name; matches the canonical
  `benchmark1`..`benchmark4` test identifiers. Maps directly to
  `attributes["test_name"]` in the Nyrkiö JSON output.
- `hz` — ops per second. Useful as a throughput metric
  (`direction: higher_is_better`, `unit: "ops/s"`).
- `mean` — **seconds per operation**. This is the field a parser
  should read for test 1's ground-truth assertion
  (`2.0 < mean < 2.3`, `unit: "s"`, `direction: lower_is_better`).
  Note the unit is seconds, not milliseconds — benchmark.js's native
  timing unit.
- `rme` — relative margin of error as a **percentage**
  (`unit: "%"`). benchmark.js computes this at the 95% confidence
  level.
- `deviation`, `variance`, `moe`, `sem` — all in **seconds** (or
  seconds² for `variance`). These come straight from
  `benchmark.stats`.
- `samples` — sample count (length of `benchmark.stats.sample`).
  benchmark.js chooses this adaptively based on `minSamples` and
  `maxTime`.
- `cycles` — the number of cycles per sample benchmark.js settled
  on during calibration.
- `deferred` — whether this benchmark ran in async deferred mode.
  `true` for benchmark1/benchmark4, `false` for benchmark2/benchmark3.
  Useful diagnostic metadata; probably lands in `extra_info`.
- `passed` — `true` unless benchmark.js reported an error or abort
  for this benchmark. Maps to the benchzoo `passed` extension at the
  top level of the per-test Nyrkiö dict.
- Top-level `month` — the UTC month (1..12) used to compute test 4's
  sleep duration at suite-build time. Lets parser tests do the
  **exact** change-detection check for test 4 instead of the loose
  `{1.15, 2.15, 3.15}` membership check.

### Recommended parser mapping

For each entry in `results[]`:

- emit one Nyrkiö dict with `attributes["test_name"] = entry.name`,
- populate `metrics` with `mean` (s, lower_is_better), `hz` (ops/s,
  higher_is_better), `rme` (%, lower_is_better), `deviation` (s,
  lower_is_better),
- stash `samples`, `cycles`, `deferred`, framework `version`, and
  top-level `month` into `extra_info`,
- set `passed = entry.passed`,
- set `timestamp = 0` (ingest layer fills it in from git).

### Node-specific gotchas

- benchmark.js 2.1.4 uses a `Benchmark.Suite` + event-emitter API
  (`cycle`, `complete`). Results must be captured in the `cycle` handler
  — there is no aggregate `results` array on the Suite after
  `complete`.
- Deferred benchmarks require `suite.run({ async: true })`; otherwise
  the event loop is blocked between synchronous cycles and
  `setTimeout` never fires.
- benchmark.js's `mean` is in **seconds**, not milliseconds — easy to
  misread against frameworks that default to ms.
- `stdout` vs. `stderr`: benchmark.js's default `String(bench)`
  human-readable output goes wherever we print it; `run.sh` keeps
  stdout clean for JSON by sending human-readable cycle lines to
  `output.log` via stderr.
