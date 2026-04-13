# mocha

[Mocha](https://mochajs.org/) is a long-standing JavaScript unit-test
runner. Mocha itself is not a benchmark framework, but its native
`--reporter json` option emits a single JSON document with per-test
`duration` fields (in milliseconds) — a perfectly usable performance
signal as long as test names are stable. See parser-targets.md
section 6 ("Unit test / QA frameworks").

This framework directory targets mocha's **native JSON reporter**, not
`mocha-junit-reporter`. A separate junit-producer parser can be added
later for the junit path if demand shows up; they are distinct output
formats and each gets its own parser per the resolved question in
[`docs/parser-targets.md`](../../../docs/parser-targets.md#resolved-questions).

## Links

- **Sample benchmark** — see [`test/sample.test.js`](test/sample.test.js)
- **Workflow** — [`.github/workflows/mocha.yml`](../../../.github/workflows/mocha.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/mocha.yml>
- **Parser** — [`src/benchzoo/parsers/mocha.py`](../../../src/benchzoo/parsers/mocha.py) *(not yet written)*
- **Parser tests** — [`tests/parsers/test_mocha.py`](../../../tests/parsers/test_mocha.py) *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) as four
Mocha `it(...)` tests inside a single `describe('sample benchmark')`
block in `test/sample.test.js`. Each `it(...)` title maps directly to
the test identifier the parser writes into `attributes["test_name"]`
(`benchmark1` .. `benchmark4`).

- **Test 1** (sleep 2.15 s) — `await` on a `setTimeout`-backed
  `sleep(2150)` helper. Real timers; mocha has no fake-timer mode of
  its own, so `setTimeout` actually blocks wall-clock for ~2.15 s.
- **Test 2** (tight CPU loop) — sums `i` into a `sink` variable across
  1000 iterations. Touching the accumulator prevents a sufficiently
  clever JS engine from eliding the loop, analogous to
  `std::hint::black_box` in Rust or `Blackhole.consume` in JMH.
- **Test 3** (write 1.4 MB to /dev/null) — allocates a `Uint8Array` of
  1,400,000 bytes and fills it byte-by-byte. Node has no ergonomic
  `/dev/null` write API; filling an in-process buffer is the closest
  equivalent and exercises the same I/O-shaped timing bucket.
- **Test 4** (monthly change point) — reads `new Date().getUTCMonth()`
  (0-based → +1), computes `2.15 + ((m % 3) - 1)`, and sleeps for that
  many seconds. Produces the step-function series described in the
  canonical sample benchmark.

`this.timeout(10000)` is set at the `describe` level so the
sleep-dominated tests (1 and 4, up to 3.15 s) never hit mocha's
default 2 s per-test timeout.

### Output format captured

The workflow captures **one** output format: mocha's native
`--reporter json`, writing `output.json` in this directory. Mocha is
pinned (`mocha@11.1.0`) per
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#versioning-the-framework).

The JSON reporter emits on **stdout**, not to a file, so `run.sh`
redirects:

```bash
npx mocha test/sample.test.js --reporter json --timeout 10000 > output.json
```

## Running locally

```bash
act push -W .github/workflows/mocha.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/mocha-output/output.json`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with Node 20 available locally you can skip `act`:

```bash
./run.sh
```

from this directory. That runs `npm install && npx mocha ... > output.json`
and produces the same `output.json`.

## Parser notes

Mocha's native JSON reporter emits **one JSON document** per run, with
the following top-level shape:

```json
{
  "stats": {
    "suites": 1,
    "tests": 4,
    "passes": 4,
    "pending": 0,
    "failures": 0,
    "start": "2026-04-13T12:00:00.000Z",
    "end":   "2026-04-13T12:00:08.500Z",
    "duration": 8500
  },
  "tests":    [ /* every test that ran, including passes, failures, pending */ ],
  "pending":  [ /* tests skipped with it.skip / xit */ ],
  "failures": [ /* tests that threw or timed out */ ],
  "passes":   [ /* tests that succeeded */ ]
}
```

Each entry inside `tests` / `passes` / `failures` / `pending` has:

| Field          | Type   | Notes                                                                       |
| -------------- | ------ | --------------------------------------------------------------------------- |
| `title`        | string | The `it(...)` title. For the sample: `"benchmark1"` .. `"benchmark4"`.      |
| `fullTitle`    | string | `describe` path + title, space-joined. E.g. `"sample benchmark benchmark1"`.|
| `file`         | string | Absolute path to the test file. Not identity-bearing; workspace-dependent.  |
| `duration`     | number | Wall-clock duration in **milliseconds**. Integer for the test runner.       |
| `currentRetry` | number | Retry count; 0 unless `this.retries(n)` is used in the test.                |
| `err`          | object | Empty `{}` on pass; populated with `message`/`stack`/`name` on failure.     |

The same test appears in both `tests` and exactly one of
`passes` / `failures` / `pending`. The parser should iterate over
`tests` once (it's the union) and derive pass/fail from whether `err`
is an empty object or carries a message — or cross-reference against
`failures[]` by `fullTitle`. The `passes` / `failures` / `pending`
arrays are redundant views over the same data, useful for quick
summaries but not needed if the parser walks `tests` directly.

For the sample benchmark in this directory (no `describe`-nesting
beyond one level and no class-like grouping), the stable identity key
is `title` — `"benchmark1"` .. `"benchmark4"` — which maps directly to
`attributes["test_name"]`. If a future fixture nests multiple
`describe` blocks, `fullTitle` becomes the more obviously unique key,
but that is a fixture-drift concern to handle when it happens, not
pre-emptively.

`duration` is in **milliseconds** — convert to seconds (or carry as ms
with `unit: "ms"`) when emitting the `duration` metric. The canonical
sample benchmark's ground truth is stated in seconds; the parser's
emitted metric should follow the same "seconds, `lower_is_better`"
convention the other unit-test-runner parsers (junit_jest,
junit_pytest) use, so downstream consumers can compare across
frameworks without unit juggling.

Failures should set `passed: false` on the result dict; the result is
still emitted, not filtered (see *Library boundaries* in
[`docs/design.md`](../../../docs/design.md)). A failed mocha test still
has a meaningful `duration` value — mocha records the wall time up to
the point of the assertion error or timeout — so the measurement stays
useful as a time series even when the test went red.

### Gotchas

- **Mocha timing precision.** `duration` is reported as an integer
  number of milliseconds. Test 2's tight CPU loop is expected to round
  to `0` or `1` ms — that is fine and expected; the value of test 2 in
  this framework is exercising the sub-millisecond floor, not producing
  a stable number. Parsers should not treat a `duration: 0` as a
  missing value.
- **`stats.start` / `stats.end` are wall-clock strings**, not commit
  timestamps. Per the
  [`timestamp` field semantics](../../../docs/design.md#field-semantics),
  the parser must leave `timestamp` at `0` and let the ingest layer
  assign the real git-commit-derived value. If the parser wants to
  preserve mocha's reported run time for reference, stash it in
  `extra_info` (e.g. `extra_info["machine_time"]`), never in
  `timestamp`.
- **Output file vs stdout.** Mocha has a `--reporter-options output=...`
  flag on some reporters, but the built-in JSON reporter ignores it and
  always writes to stdout. `run.sh` redirects stdout into `output.json`.
  Don't be fooled by stale documentation suggesting the option works
  here.
