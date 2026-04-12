# vitest-bench

[Vitest](https://vitest.dev/)'s built-in benchmark mode
(`vitest bench`). Vitest is the modern test runner for the Vite
ecosystem; its bench mode wraps [tinybench](https://github.com/tinylibs/tinybench)
and is becoming the default micro-benchmark tool in TypeScript and
JavaScript codebases.

## Links

- **Sample benchmark** — [`sample-benchmark.bench.ts`](sample-benchmark.bench.ts),
  orchestrated by [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/vitest-bench.yml`](../../../.github/workflows/vitest-bench.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/vitest-bench.yml>
- **Parser** — [`src/benchzoo/parsers/vitest_bench.py`](../../../src/benchzoo/parsers/vitest_bench.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_vitest_bench.py`](../../../tests/parsers/test_vitest_bench.py) *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
vitest-bench idiom. All four tests live in the single
`sample-benchmark.bench.ts` file, grouped under one `describe(...)`
block so they share a suite name in the JSON output.

### Per-test mapping

- **Test 1** (sleep 2.15 s) — async `bench('benchmark1', async () =>
  { await new Promise(r => setTimeout(r, 2150)); }, { iterations: 3, warmupIterations: 0, time: 0, warmupTime: 0 })`.
  Clamped to three iterations because tinybench's default is to keep
  running until a minimum time budget (~500 ms) elapses — which for a
  2.15 s sleep would run hundreds of iterations and take many minutes.
  Three iterations still gives the parser a distribution with a real
  stddev.
- **Test 2** (tight CPU loop) — `for (let i = 0; i < 1000; i++) sum +=
  i`, accumulated into a module-scoped `sum` sink so V8 cannot elide
  the loop as dead code. Left with tinybench defaults (runs for the
  default time budget, producing hundreds of samples) — the loop body
  is sub-microsecond, so we want many iterations for stable stats.
- **Test 3** (write 1.4 MB to /dev/null) — allocates a 1,400,000-byte
  `ArrayBuffer`, wraps it in a `Uint8Array`, and sparsely writes one
  byte every 4096 bytes. Follows the same synthetic, memory-only
  adaptation as the k6 framework entry (Vitest does have `fs` access,
  but the ArrayBuffer shape keeps the measurement comparable across
  JS frameworks and avoids the OS-specific `/dev/null` path). The
  byte count is preserved (1,400,000 exactly) so the ground-truth
  magnitude is the same, but the physical operation is not disk I/O
  and should not be compared on the I/O axis across frameworks.
- **Test 4** (monthly change point) — computes
  `2.15 + ((UTC month mod 3) - 1)` in JavaScript at module load, then
  sleeps for that many seconds via `setTimeout`. Same
  `{ iterations: 3, time: 0 }` clamp as test 1. Same change-point
  structure as every other framework's test 4.

## Running locally

```bash
act push -W .github/workflows/vitest-bench.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/vitest-bench-output/output.json`.
See [`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with Node 20+ installed locally, you can bypass `act`
entirely and just run `bash run.sh` from this directory.

## Parser notes

Vitest is pinned to `2.1.8`. Its `--reporter=json` output in bench
mode is a single top-level JSON object written to `output.json`.

### Output shape

Vitest's JSON reporter is an adaptation of the Jest JSON reporter shape,
with bench-specific data grafted on. Roughly:

```jsonc
{
  "numTotalTestSuites": 1,
  "numTotalTests": 4,
  "numPassedTests": 4,
  "numFailedTests": 0,
  "startTime": 1735680000000,
  "success": true,
  "testResults": [
    {
      "name": "/abs/path/to/sample-benchmark.bench.ts",
      "status": "passed",
      "message": "",
      "startTime": 1735680000000,
      "endTime": 1735680008000,
      "assertionResults": [
        {
          "ancestorTitles": ["benchzoo canonical sample benchmark"],
          "fullName": "benchzoo canonical sample benchmark > benchmark1",
          "title": "benchmark1",
          "status": "passed",
          "duration": 6450
        }
      ]
    }
  ]
}
```

Each `bench(...)` call lands as one `assertionResults[]` entry. The
`title` is the bench name (`benchmark1`..`benchmark4`); the
`ancestorTitles` array is the `describe(...)` chain.

### tinybench stats

Because vitest bench is a thin layer over tinybench, the per-bench
Task stats (mean, min, max, variance, sd, sem, df, critical, moe, rme,
p75, p99, p995, p999, hz, period, samples) should be attached to each
assertion. Vitest's JSON reporter puts them under a key such as
`benchmark` or similar inside each assertion — the first task for the
parser author is to dump a real captured `output.json` and see where
they live (the Vitest JSON schema is not formally documented and has
shifted between minor versions). Grepping the fixture for `2150` or
`2.15` points directly at test 1's mean in whichever units Vitest
chose (milliseconds is the tinybench default).

Recommended parser shape once the exact key path is confirmed:

- Emit one result dict per `assertionResults[]` entry with a title
  matching one of `benchmark1`..`benchmark4`.
- Set `attributes["test_name"]` to the `title`.
- Populate `metrics` with `mean`, `min`, `max`, `p75`, `p99`, and `hz`
  (hz = operations per second). Use `unit: "ms"` for the time metrics
  (tinybench reports in ms by default) and `unit: "ops/s"` for hz.
  Set `direction: "lower_is_better"` for times and
  `"higher_is_better"` for hz.
- Stash `samples` (iteration count) and `rme` (relative margin of
  error, percent) in `extra_info`.
- `describe(...)` titles go into `extra_info["group"]` per the data
  model rule that classification metadata is `extra_info`, not
  `attributes`.

### Failures

Vitest's bench mode does not have assertions inside the bench body in
the normal sense — a bench passes if its callback doesn't throw. If
the callback does throw, the assertion `status` is `"failed"` and the
parser should emit `passed: false` for that entry.

### Timestamps

Vitest's output carries `startTime` / `endTime` (epoch milliseconds).
**These must not be used for the Nyrkiö `timestamp` field** — per the
parser contract in
[`docs/design.md`](../../../docs/design.md#field-semantics), parsers
always set `timestamp: 0` and leave the real timestamp to the ingest
layer. Stash the wall-clock values in `extra_info` if they're useful
for reference.
