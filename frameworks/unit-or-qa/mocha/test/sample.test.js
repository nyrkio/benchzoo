// Canonical sample benchmark expressed as four Mocha unit tests.
//
// Mocha itself is a unit-test runner, not a benchmark framework. We use it
// here as a "unit test runner as timing source" per
// docs/parser-targets.md section 6: mocha's native `--reporter json` emits
// one JSON document with per-test `duration` (in milliseconds) for every
// test, and when test names are stable that is a perfectly usable
// performance time series.
//
// NOTE: this file uses mocha's native JSON reporter — NOT mocha-junit-reporter.
// The captured output is a single JSON document, not JUnit XML. See the
// README's "Parser notes" section for the shape.

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

describe('sample benchmark', function () {
  // Per-test timeout bumped above mocha's 2 s default so the sleep-dominated
  // tests (1 and 4, up to 3.15 s) don't hit the timeout.
  this.timeout(10000);

  it('benchmark1', async function () {
    // Sleep-dominated: ~2.15 s wall time.
    await sleep(2150);
  });

  it('benchmark2', function () {
    // Tight CPU loop, sub-millisecond. JavaScript engines can optimize
    // empty loops; touching `sink` keeps the body observable.
    let sink = 0;
    for (let i = 0; i < 1000; i++) {
      sink += i;
    }
    if (sink !== 499500) throw new Error('sink mismatch');
  });

  it('benchmark3', function () {
    // Allocate and fill 1.4 MB. Node has no direct /dev/null write API
    // worth using here; allocating and filling an ArrayBuffer is the
    // closest in-process analogue and exercises the same I/O-shaped
    // timing bucket as the bash reference.
    const N = 1_400_000;
    const buf = new Uint8Array(N);
    for (let i = 0; i < N; i++) {
      buf[i] = i & 0xff;
    }
    if (buf.length !== N) throw new Error('length mismatch');
  });

  it('benchmark4', async function () {
    // Monthly change-point showcase. sleep_s = 2.15 + ((m mod 3) - 1),
    // with m the current UTC month (1..12). See
    // docs/sample-benchmark.md test 4.
    const m = new Date().getUTCMonth() + 1; // getUTCMonth is 0-based
    const sleepS = 2.15 + ((m % 3) - 1);
    await sleep(Math.round(sleepS * 1000));
  });
});
