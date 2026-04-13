# playwright

[Playwright](https://playwright.dev/) is Microsoft's end-to-end browser
test runner for web apps. Although its headline use case is driving
Chromium / Firefox / WebKit, Playwright is also a general-purpose test
runner whose `--reporter=json` output records per-test wall time in a
rich nested tree — a perfectly usable performance signal whenever test
names are stable. See parser-targets.md section 6 ("Unit test / QA
frameworks").

## Links

- **Sample benchmark** — see [`tests/sample.spec.ts`](tests/sample.spec.ts)
  and [`playwright.config.ts`](playwright.config.ts)
- **Workflow** — [`.github/workflows/playwright.yml`](../../../.github/workflows/playwright.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/playwright.yml>
- **Parser** — [`src/benchzoo/parsers/playwright.py`](../../../src/benchzoo/parsers/playwright.py) *(not yet written)*
- **Parser tests** — [`tests/parsers/test_playwright.py`](../../../tests/parsers/test_playwright.py) *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) as four
Playwright tests in a single `tests/sample.spec.ts` file. Each
`test('benchmarkN', ...)` maps directly to the identifier the parser
will write into `attributes["test_name"]` (`benchmark1` .. `benchmark4`).

- **Test 1** (sleep 2.15 s) — `await` on a `setTimeout`-backed
  `sleep(2150)` helper.
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

### Adaptation: no browser navigation

Playwright is a browser-automation-first tool, but the canonical sample
benchmark is not browser-y — it's a sleep, a CPU loop, a buffer
allocation, and a month-based sleep. Rather than paper over the mismatch
with a pro-forma `page.goto('about:blank')` in each test body, these
tests do the work directly. Playwright is used purely as a test runner
here; the chromium browser binary still gets installed in CI because
Playwright requires at least one project (see
[`playwright.config.ts`](playwright.config.ts)) and the worker machinery
expects the browser to be installable, but no test ever touches a `page`
object.

A future variant that *does* navigate (e.g. `page.goto('about:blank')`
before the work) would be a worthwhile second fixture if parser authors
want to exercise the fields Playwright populates only when a page is
actually loaded — but for timing-extraction purposes the current
browserless shape is sufficient.

The per-test timeout is set to 10 s in `playwright.config.ts` so the
sleep-dominated tests (1 and 4, up to 3.15 s) never hit Playwright's
default 30 s timeout unexpectedly — and, conversely, a hang won't
silently consume the full 30 s before failing.

### Output format captured

The workflow captures **one** output format: the built-in JSON reporter,
configured in `playwright.config.ts` as:

```ts
reporter: [['json', { outputFile: 'output.json' }]]
```

so `npx playwright test` writes `./output.json` with no extra flags.
`@playwright/test` is pinned (`1.49.0`) per
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#versioning-the-framework).

## Running locally

```bash
act push -W .github/workflows/playwright.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/playwright-output/output.json`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with Node 20 available locally you can skip `act`:

```bash
./run.sh
```

from this directory. That runs `npm install && npx playwright install
--with-deps chromium && npx playwright test` and produces the same
`output.json`.

## Parser notes

Playwright's JSON reporter emits a **nested tree**, not a flat list —
the shape is richer than `jest-junit`'s flat `<testcase>` sequence.
Top-level keys include `config`, `suites`, `errors`, and `stats`. The
interesting path for a parser is:

```
suites[]                  // one per top-level file / directory
  .specs[]                // individual test() calls within the suite
    .tests[]              // one per (spec × project) — parametrized by
                          //   browser project. We configure a single
                          //   chromium project, so there's exactly one
                          //   `tests[]` entry per spec here, but the
                          //   parser must handle N in general.
      .results[]          // one per retry attempt. Most runs have one
                          //   result; retries produce more.
```

Each entry in `results[]` carries `status` (`"passed"`, `"failed"`,
`"timedOut"`, `"skipped"`, `"interrupted"`), `duration` in
**milliseconds** (integer), `workerIndex`, `retry`, and assorted error
info. The natural `test_name` is `specs[].title` (which is the string
passed to `test(...)` — `"benchmark1"` etc.). The natural wall-time
metric is `results[0].duration` with `unit: "ms"` and
`direction: "lower_is_better"`.

Parametrization: because `tests[]` is one-per-project, a test run that
uses multiple browser projects produces multiple entries. The parser
should either:

- stash the project name in `extra_info["project"]` and emit one
  Nyrkiö dict per `(spec, project)` pair, or
- require unique `test_name`s by concatenating
  (`"benchmark1[chromium]"`), analogous to pytest's parametrize id
  conventions.

The sample benchmark here uses a single chromium project, so this
choice doesn't affect the fixture — but the parser must make it
consistently.

Retries: if a test retries (unusual on a green CI run, but possible),
`results[]` will have more than one entry. The last element is the
final attempt. The parser's choice of "which result counts" should be
documented; the simplest rule is to take the final result's `duration`
and `status`.

Failures: a `status` other than `"passed"` should set `passed: false`
on the result dict. Per the
[library-boundaries rule](../../../docs/design.md), the result is still
emitted, not filtered.

### Gotchas

- **Duration precision.** `duration` is an integer number of
  milliseconds. Test 2's tight CPU loop will almost certainly round to
  `0` or `1` ms — that is fine and expected; the value of test 2 in
  this framework is exercising the sub-millisecond floor, not producing
  a stable number.
- **`startTime` is wall-clock, not `timestamp`.** Each `result` carries
  a `startTime` ISO 8601 string. Per the design-doc field semantics,
  parsers always set `timestamp: 0` and let the ingest layer fill in
  the git-derived value. If a parser wants to preserve Playwright's
  wall-clock start for reference, stash it in
  `extra_info["start_time"]` as a string.
- **Skipped tests.** Playwright emits `status: "skipped"` entries with
  `duration: 0`. Whether to emit these as Nyrkiö dicts at all is a
  parser-layer judgment call; recording them with `passed: true` and
  `extra_info["skipped"] = true` is one reasonable option.
