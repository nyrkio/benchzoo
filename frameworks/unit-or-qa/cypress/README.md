# cypress

[Cypress](https://www.cypress.io/) is a JavaScript end-to-end test
runner that drives a real browser (bundled Electron by default).
Cypress itself is not a benchmark framework, but because it uses Mocha
internally, the [`mocha-junit-reporter`](https://github.com/michaelleeallen/mocha-junit-reporter)
plugin emits standard JUnit XML with a per-testcase `time` attribute —
a perfectly usable performance signal as long as test names are stable.
See parser-targets.md section 6 ("Unit test / QA frameworks").

## Links

- **Sample benchmark** — see [`cypress/e2e/sample.cy.js`](cypress/e2e/sample.cy.js)
- **Workflow** — [`.github/workflows/cypress.yml`](../../../.github/workflows/cypress.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/cypress.yml>
- **Parser** — [`src/benchzoo/parsers/junit_cypress.py`](../../../src/benchzoo/parsers/junit_cypress.py) *(not yet written)*
- **Parser tests** — [`tests/parsers/test_junit_cypress.py`](../../../tests/parsers/test_junit_cypress.py) *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) as four
Cypress end-to-end tests inside a single `describe(...)` block in
`cypress/e2e/sample.cy.js`. Each `it(...)` call maps directly to the
test identifier the parser writes into `attributes["test_name"]`
(`benchmark1` .. `benchmark4`).

Every test begins with `cy.visit('about:blank')` as a trivial first
step so Cypress has a page attached; the tests do not exercise any
real HTTP target.

- **Test 1** (sleep 2.15 s) — `cy.wait(2150)`. Uses Cypress's built-in
  wait rather than `setTimeout` so the sleep sits inside the command
  queue and wall time is attributed to the test.
- **Test 2** (tight CPU loop) — sums `i` into a `sink` variable across
  1000 iterations, inside a `cy.then(() => { ... })` callback.
  Touching the accumulator prevents a sufficiently clever JS engine
  from eliding the loop, analogous to `std::hint::black_box` in Rust
  or `Blackhole.consume` in JMH.
- **Test 3** (write 1.4 MB to /dev/null) — allocates a `Uint8Array` of
  1,400,000 bytes and fills it byte-by-byte inside a `cy.then()`.
  Neither the browser nor the Cypress runner has an ergonomic
  `/dev/null` write API; filling an in-process buffer is the closest
  equivalent and exercises the same I/O-shaped timing bucket.
- **Test 4** (monthly change point) — reads `new Date().getUTCMonth()`
  (0-based → +1), computes `2.15 + ((m % 3) - 1)`, and `cy.wait`s for
  that many milliseconds. Produces the step-function series described
  in the canonical sample benchmark.

### Output format captured

The workflow captures **one** output format: JUnit XML via
`mocha-junit-reporter`. The reporter is configured inside
`cypress.config.js` at the top level of the exported config:

```js
reporter: 'mocha-junit-reporter',
reporterOptions: {
  mochaFile: 'output.xml',
  toConsole: false,
},
```

so `npx cypress run --headless --browser=electron` writes
`./output.xml` with no extra flags. Both Cypress and
`mocha-junit-reporter` are pinned (`cypress@14.0.0`,
`mocha-junit-reporter@2.2.1`) per
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#versioning-the-framework).

## Running locally

```bash
act push -W .github/workflows/cypress.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/cypress-output/output.xml`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with Node 20 and the required system libraries available
locally (see the workflow for the apt list, or use Cypress's official
Docker images), you can skip `act`:

```bash
./run.sh
```

from this directory. That runs `npm install && npx cypress run
--headless --browser=electron` and produces the same `output.xml`.

## Parser notes

`mocha-junit-reporter` emits **standard JUnit XML**:
`<testsuites>/<testsuite>/<testcase>` with a `time` attribute on each
`<testcase>` giving wall-clock duration in seconds. Failures appear as
`<failure>` or `<error>` children on the relevant `<testcase>`. The
XML shape is essentially identical to what `jest-junit` emits, so the
`junit_cypress` parser is expected to be a thin wrapper around the
shared junit helper (or may simply delegate to `junit_vanilla`) —
`mocha-junit-reporter`'s output is vanilla-ish JUnit.

Cross-reference:
[`src/benchzoo/parsers/junit_jest.py`](../../../src/benchzoo/parsers/junit_jest.py)
and
[`src/benchzoo/parsers/junit_vanilla.py`](../../../src/benchzoo/parsers/junit_vanilla.py).
The three parsers share the same junit XML shape and most of the same
extraction logic; they differ primarily in how they derive
`attributes["test_name"]` from `classname`/`name`:

- `junit_jest` reads `name` directly.
- `junit_cypress` likewise reads `name` directly — Mocha/Cypress's
  `it('benchmark1', ...)` records `name="benchmark1"` with no prefix
  to strip. `classname` from `mocha-junit-reporter` is the enclosing
  `describe(...)` path (here, `"benchzoo sample benchmark"`); the
  sample uses a single top-level describe, so `classname` can be
  ignored for identity purposes — `name` alone is the stable key.
  (If the parser wants to stash the describe path anywhere, a
  reasonable home is `extra_info["suite"]`.)

Failures should set `passed: false` on the result dict (same rule as
`junit_jest`); the result is still emitted, not filtered (see
*Library boundaries* in [`docs/design.md`](../../../docs/design.md)).

### Gotchas

- **Mocha/Cypress timing precision.** `mocha-junit-reporter`'s `time`
  attribute is reported in seconds with sub-millisecond precision (a
  few decimal places — the exact width depends on reporter version).
  Test 2's tight CPU loop is expected to round to a very small number
  — that is fine and expected; the value of test 2 in this framework
  is exercising the sub-millisecond floor, not producing a stable
  number.
- **`cy.wait` vs `setTimeout`.** Cypress commands queue; a bare
  `setTimeout` inside a test body runs outside the queue and its
  duration is not attributed to the test reliably. The sample uses
  `cy.wait(ms)` for all sleeps.
- **CI system dependencies.** Cypress drives a real browser (bundled
  Electron) and therefore needs a handful of X / GTK libraries on the
  runner. The workflow uses the official
  [`cypress-io/github-action`](https://github.com/cypress-io/github-action)
  which handles the install transparently. If reproducing by hand on
  a minimal Ubuntu image, install
  `libgtk2.0-0 libgtk-3-0 libgbm-dev libnotify-dev libnss3 libxss1
  libasound2 libxtst6 xauth xvfb`.
