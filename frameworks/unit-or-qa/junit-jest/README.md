# junit-jest

[Jest](https://jestjs.io/) is JavaScript's dominant unit-test runner.
Jest itself is not a benchmark framework, but when combined with the
[`jest-junit`](https://github.com/jest-community/jest-junit) reporter it
emits standard JUnit XML with a per-testcase `time` attribute — a
perfectly usable performance signal as long as test names are stable.
See parser-targets.md section 6 ("Unit test / QA frameworks").

## Links

- **Sample benchmark** — see [`sample.test.js`](sample.test.js)
- **Workflow** — [`.github/workflows/junit-jest.yml`](../../../.github/workflows/junit-jest.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/junit-jest.yml>
- **Parser** — [`src/benchzoo/parsers/junit_standard.py`](../../../src/benchzoo/parsers/junit_standard.py) — shared with `junit-vanilla`, `ctest`, and `catch2`'s junit reporter
- **Parser tests** — `tests/parsers/test_batch2.py::test_junit_standard_jest`

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) as four
Jest unit tests in a single `sample.test.js` file. Each `test(...)` call
maps directly to the test identifier the parser writes into
`attributes["test_name"]` (`benchmark1` .. `benchmark4`).

- **Test 1** (sleep 2.15 s) — `await` on a `setTimeout`-backed
  `sleep(2150)` helper. Real timers; jest's fake timers are **off**
  (the file never calls `jest.useFakeTimers()`), so the setTimeout
  actually blocks wall-clock for ~2.15 s.
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

`jest.setTimeout(10_000)` is set at the top of the file so the
sleep-dominated tests (1 and 4, up to 3.15 s) never hit Jest's default
5 s per-test timeout.

### Output format captured

The workflow captures **one** output format: JUnit XML via
`jest-junit`. `jest-junit` is configured inside `package.json` under
the top-level `"jest-junit"` key:

```json
"jest-junit": {
  "outputDirectory": "./",
  "outputName": "output.xml"
}
```

so `npx jest --reporters=default --reporters=jest-junit` writes
`./output.xml` with no extra flags. Both Jest and `jest-junit` are
pinned (`jest@29.7.0`, `jest-junit@16.0.0`) per
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#versioning-the-framework).

## Running locally

```bash
act push -W .github/workflows/junit-jest.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/junit-jest-output/output.xml`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with Node 20 available locally you can skip `act`:

```bash
./run.sh
```

from this directory. That runs `npm install && npx jest` and produces
the same `output.xml`.

## Parser notes

`jest-junit` emits **standard JUnit XML**:
`<testsuites>/<testsuite>/<testcase>` with a `time` attribute on each
`<testcase>` giving wall-clock duration in seconds. Failures appear as
`<failure>` or `<error>` children on the relevant `<testcase>`.

Unlike pytest-benchmark's junit output, `jest-junit` does **not**
augment testcases with benchmark-stat `<properties>` — there is no
`min`/`max`/`mean`/`stddev` to extract. The only metric available is
the single wall-clock `time` attribute, so the `junit_standard` parser
takes the same fallback path as `junit_pytest` takes when properties
are absent: emit one `duration` metric with `unit: "s"` and
`direction: "lower_is_better"` per testcase.

Cross-reference: [`src/benchzoo/parsers/junit_pytest.py`](../../../src/benchzoo/parsers/junit_pytest.py).
The two parsers share the same junit XML shape and most of the same
extraction logic; they differ primarily in how they derive
`attributes["test_name"]` from `classname`/`name`:

- `junit_pytest` strips a leading `test_` from `name` (pytest's
  conventional prefix) so `test_benchmark1` → `"benchmark1"`.
- `junit_standard` reads `name` directly — Jest's `test('benchmark1', ...)`
  records `name="benchmark1"` with no prefix to strip. `classname`
  from `jest-junit` is the suite describe-path (or the filename when
  no `describe` wraps the test); the sample here uses no `describe`
  block, so `classname` is the file's derived suite name and can be
  ignored for identity purposes — `name` alone is the stable key.

Failures should set `passed: false` on the result dict (same rule as
`junit_pytest`); the result is still emitted, not filtered (see
*Library boundaries* in [`docs/design.md`](../../../docs/design.md)).

### Gotchas

- **Jest timing precision.** `jest-junit`'s `time` attribute is
  reported in seconds to three decimal places (millisecond precision).
  Test 2's tight CPU loop is expected to round to `0.000` or `0.001` —
  that is fine and expected; the value of test 2 in this framework is
  exercising the sub-millisecond floor, not producing a stable number.
- **Fake timers must stay off.** If a future test in this file calls
  `jest.useFakeTimers()`, tests 1 and 4's `setTimeout` will advance
  instantly under the mock clock and the captured wall times will be
  wrong. The comment at the top of `sample.test.js` flags this.
