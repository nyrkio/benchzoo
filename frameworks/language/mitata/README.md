# mitata

[mitata](https://github.com/evanwashere/mitata) is a modern JavaScript
micro-benchmark library pitched as a faster / nicer-API alternative to
tinybench. It runs on Node, Deno, and Bun, and exposes a small surface
area: `bench(name, fn)` to register benchmarks and `run(options)` to
execute them. By default `run()` prints a formatted console table;
`run({ json: true })` returns a structured results object that we
capture verbatim.

## Links

- **Sample benchmark** — [`sample-benchmark.js`](sample-benchmark.js),
  orchestrated by [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/mitata.yml`](../../../.github/workflows/mitata.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/mitata.yml>
- **Parser** — `src/benchzoo/parsers/mitata.py` *(not yet written)*
- **Parser tests** — `tests/parsers/test_mitata.py` *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
mitata idiom. All four tests are registered via top-level
`bench('benchmarkN', ...)` calls, then a single `await run({ json:
true })` executes the whole suite.

### Per-test mapping

- **Test 1** (sleep 2.15 s) — async callback
  `async () => { await new Promise(r => setTimeout(r, 2150)); }`.
  See "Time-budget control" below for why this test drives the bulk
  of the suite's wall time.
- **Test 2** (tight CPU loop) — synchronous `for (let i = 0; i <
  1000; i++) sum += i;`, accumulated into a module-scoped sink so
  V8 cannot elide the loop.
- **Test 3** (write 1.4 MB to /dev/null) — allocates a 1,400,000-byte
  `ArrayBuffer`, wraps it in a `Uint8Array`, and sparsely writes one
  byte every 4096 bytes. Same synthetic memory adaptation as
  tinybench, vitest-bench, and k6 — mitata is runtime-agnostic
  (Node, Deno, Bun), so we avoid Node-specific `fs` calls. Byte
  count preserved exactly so the ground-truth magnitude matches.
- **Test 4** (monthly change point) — computes
  `2.15 + ((UTC month mod 3) - 1)` at module load and sleeps for
  that duration via `setTimeout`. The chosen month is emitted into
  the output JSON under the top-level `month` key so fixtures are
  self-describing and parser tests can do the **exact**
  change-detection check instead of the loose `{1.15, 2.15, 3.15}`
  membership check.

### Time-budget control

**mitata has no fixed-iterations option comparable to tinybench's
`{ iterations: 3 }`.** Its sampling loop is time-bounded: for each
`bench`, it keeps invoking the callback until a minimum sample count
and a minimum elapsed time have both been satisfied. For
sub-microsecond bodies (tests 2 and 3) that's exactly what you want —
it gives many thousands of samples and tight stats. For
sleep-dominated bodies (tests 1 and 4) it is not what you want: a
2-second callback sampled to mitata's default budget can take ~30 s
per test.

Where supported, we hint per-bench options (e.g. `min_samples: 3`,
`gc: 'inner'`) to bound the sleepy tests. If the installed mitata
version does not honor those options, the whole suite will still
converge — it will just take longer. CI wall time for this workflow
is therefore expected to be **~15-60 seconds**, dominated by tests 1
and 4. This is documented so nobody is surprised when the workflow
takes noticeably longer than tinybench's.

## Running locally

```bash
act push -W .github/workflows/mitata.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/mitata-output/output.json`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with Node 20+ installed locally, `bash run.sh` from
this directory runs the suite directly.

## Parser notes

### Not yet written

The Python parser is not yet written. The exact JSON shape returned
by `run({ json: true })` is the load-bearing unknown here — mitata's
documentation is light, and the shape has changed across releases.
The description below is our best reasoning from first principles and
from reading the mitata source on GitHub; **the real shape will be
pinned down once CI captures the first live fixture**, and this
README (plus any parser) refined accordingly.

### Output format: `output.json`

mitata is a *library*, not a runner — there is no canonical file
output format. `sample-benchmark.js` itself defines the outer
envelope emitted on stdout and `run.sh` redirects it to `output.json`.
The outer envelope is stable:

```json
{
  "framework": "mitata",
  "version": "1.0.34",
  "month": 4,
  "results": { ... whatever run({ json: true }) returned ... }
}
```

The **inner `results` object is what mitata itself emits** and is the
piece that may shift between versions. Based on the mitata 1.x source,
we expect something in the neighborhood of:

```json
{
  "benchmarks": [
    {
      "alias": "benchmark1",
      "group": null,
      "runs": [
        {
          "stats": {
            "samples": 3,
            "min": 2149.9,
            "max": 2150.4,
            "avg": 2150.1,
            "p25": 2150.0,
            "p50": 2150.1,
            "p75": 2150.3,
            "p99": 2150.4,
            "p999": 2150.4
          }
        }
      ]
    }
  ]
}
```

Key unknowns the parser will need to resolve once a real fixture is
captured:

- **Top-level key name** — `benchmarks`, `results`, or `tasks`?
- **Per-benchmark name field** — `alias`, `name`, or `title`?
- **Whether runs are wrapped in a `runs[]` array** (to support mitata
  groups / parametrized benches) or flattened.
- **Stats field names** — `avg` vs `mean`, `p999` vs `p99_9`, etc.
- **Unit** — mitata internally measures in **nanoseconds**; it is not
  yet confirmed whether the JSON export is in nanoseconds or
  milliseconds. See "Units" below.

**To be refined once CI captures the first real fixture.**

### Units

mitata's internal stats are believed to be in **nanoseconds** (its
console formatter applies unit scaling at display time). If the JSON
export preserves the raw nanosecond values, ground truth for test 1
is that the `avg`/`mean` field should fall between `2_000_000_000`
and `2_300_000_000`, i.e. the assertion is `2e9 < avg < 2.3e9` with
`unit: "ns"`.

If instead the JSON export is pre-scaled (e.g. to milliseconds), the
ground-truth assertion window moves to `2000 < avg < 2300` with
`unit: "ms"`.

**To be confirmed once CI captures the first real fixture** — at that
point this section becomes a statement of fact rather than a
conditional.

### Recommended parser mapping

For each entry in the benchmarks list:

- emit one Nyrkiö dict with `attributes["test_name"] =
  entry.alias` (or whichever name field mitata uses),
- populate `metrics` with `avg`/`mean`, `min`, `max`, `p75`, `p99`,
  `p999` (direction `lower_is_better`), plus an ops/s metric if
  mitata exposes one,
- stash `samples` count, `group`, framework `version`, and top-level
  `month` in `extra_info`,
- set `passed = true` unless mitata surfaces an error field for the
  benchmark,
- set `timestamp = 0` (ingest layer fills it in from git).

### Failures

mitata's error-surfacing behavior in `{ json: true }` mode is not
yet documented here. The canonical sample benchmark does not
exercise a failing path. To be pinned down alongside the rest of
the output shape once CI captures a fixture.
