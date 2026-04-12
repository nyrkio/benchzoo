# tinybench

[tinybench](https://github.com/tinylibs/tinybench) is a modern, minimal
JavaScript micro-benchmark library. It is the engine that Vitest's
`bench` mode wraps — here we use it directly as a standalone Node
script, so the captured output is tinybench's own per-task statistics
rather than Vitest's JSON-reporter envelope.

## Links

- **Sample benchmark** — [`sample-benchmark.js`](sample-benchmark.js),
  orchestrated by [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/tinybench.yml`](../../../.github/workflows/tinybench.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/tinybench.yml>
- **Parser** — `src/benchzoo/parsers/tinybench.py` *(not yet written —
  may end up sharing logic with `vitest_bench` since both ultimately
  consume the same tinybench `Task.result` stats shape)*
- **Parser tests** — `tests/parsers/test_tinybench.py` *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
tinybench idiom. All four tests are added to a single `Bench` instance
as `benchmark1`..`benchmark4`.

### Per-test mapping

- **Test 1** (sleep 2.15 s) — async callback
  `async () => { await new Promise(r => setTimeout(r, 2150)); }`.
  The `Bench` is constructed with `{ iterations: 3 }` so the three
  iterations across the suite keep the sleep-dominated tests bounded
  — tinybench's default would keep invoking the callback until a
  minimum time budget elapses, which for a 2-second callback means
  many minutes.
- **Test 2** (tight CPU loop) — synchronous `for (let i = 0; i <
  1000; i++) sum += i;`, accumulated into a module-scoped sink so
  V8 cannot elide the loop. Three iterations is not ideal for a
  sub-microsecond body (more iterations would give a smaller rme)
  but tinybench's iteration count is a per-`Bench` setting, not
  per-task, so we share the sleepy tests' clamp.
- **Test 3** (write 1.4 MB to /dev/null) — allocates a 1,400,000-byte
  `ArrayBuffer`, wraps it in a `Uint8Array`, and sparsely writes one
  byte every 4096 bytes. Same synthetic memory adaptation as
  vitest-bench and k6 — tinybench is runtime-agnostic (Node, Deno,
  Bun, browser), so we avoid Node-specific `fs` calls. Byte count
  preserved exactly so the ground-truth magnitude matches.
- **Test 4** (monthly change point) — computes
  `2.15 + ((UTC month mod 3) - 1)` at module load and sleeps for
  that duration via `setTimeout`. The chosen month is emitted into
  the output JSON under the top-level `month` key so fixtures are
  self-describing and parser tests can do the **exact**
  change-detection check instead of the loose `{1.15, 2.15, 3.15}`
  membership check.

## Running locally

```bash
act push -W .github/workflows/tinybench.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/tinybench-output/output.json`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with Node 20+ installed locally, `bash run.sh` from
this directory runs the suite directly.

## Parser notes

### Not yet written

The Python parser is not yet written. Because tinybench is the engine
underlying Vitest's bench mode, the per-task stats it exposes are the
**same shape** as the stats Vitest surfaces per assertion (see the
[vitest-bench README](../vitest-bench/README.md#tinybench-stats)). The
two parsers may end up sharing a helper that turns a `Task.result`-like
dict into a Nyrkiö `metrics` list; the outer framing differs (vitest
wraps tinybench stats in its Jest-style JSON reporter envelope, while
tinybench emits them directly), but the per-test numbers are the same.

### Output format: `output.json`

tinybench is a *library*, not a runner — there is no canonical file
output format. `sample-benchmark.js` itself defines the JSON shape
emitted on stdout and `run.sh` redirects it to `output.json`. The shape:

```json
{
  "framework": "tinybench",
  "version": "3.0.6",
  "month": 4,
  "results": [
    {
      "name": "benchmark1",
      "mean": 2150.1,
      "min": 2149.9,
      "max": 2150.4,
      "variance": 0.05,
      "sd": 0.22,
      "sem": 0.13,
      "df": 2,
      "critical": 4.303,
      "moe": 0.56,
      "rme": 0.026,
      "hz": 0.4651,
      "period": 2150.1,
      "p75": 2150.3,
      "p99": 2150.4,
      "p995": 2150.4,
      "p999": 2150.4,
      "samples": [2149.9, 2150.1, 2150.4],
      "totalTime": 6450.4
    }
  ]
}
```

Each entry in `results[]` is one call to `bench.add(name, fn)` —
`name` is the `benchmark1`..`benchmark4` identifier; the remaining
fields are spread directly from the task's `Task.result` and carry
tinybench's rich per-task statistics.

### Units

tinybench reports all time-based statistics in **milliseconds** —
`mean`, `min`, `max`, `sd`, `sem`, `moe`, `period`, `p75`, `p99`,
`p995`, `p999`, `totalTime`, and each element of `samples[]` are
milliseconds; `variance` is milliseconds². `hz` is operations per
second (`ops/s`), and `rme` is relative margin of error as a
**fraction** (not a percentage — multiply by 100 if you want the
`%`-style number that benchmark.js emits). This is the same unit
convention as Vitest's bench mode, since both read the same
tinybench `Task.result`.

Ground truth for test 1: `mean` should fall between 2000 and 2300
(milliseconds), i.e. the assertion is `2000 < mean < 2300` with
`unit: "ms"` — note this is **different from benchmark.js**, whose
`mean` is in seconds.

### Recommended parser mapping

For each entry in `results[]`:

- emit one Nyrkiö dict with `attributes["test_name"] = entry.name`,
- populate `metrics` with `mean`, `min`, `max`, `p75`, `p99`, `p999`,
  and `sd` (all `unit: "ms"`, `direction: "lower_is_better"`), plus
  `hz` (`unit: "ops/s"`, `direction: "higher_is_better"`),
- stash `samples` (array length, i.e. iteration count), `rme`, and
  framework `version` / top-level `month` in `extra_info`,
- set `passed = true` (tinybench raises on callback errors rather
  than recording them on the task — if the suite produced results,
  they all passed),
- set `timestamp = 0` (ingest layer fills it in from git).

### Failures

tinybench attaches an `error` to a `Task` when its callback throws,
and `task.result` may be `undefined` in that case. The emit script
here spreads `...t.result` blindly — if a task errored, that entry
will have only `name` and the parser should treat it as
`passed: false`. The canonical sample benchmark does not exercise
this path.
