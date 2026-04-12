// Canonical sample benchmark expressed as four Jest unit tests.
//
// Jest itself is a unit-test runner, not a benchmark framework. We use it
// here as a "unit test runner as timing source" per
// docs/parser-targets.md section 6: jest-junit records per-testcase wall
// time in the JUnit XML's `time` attribute, and when test names are stable
// that is a perfectly usable performance time series.
//
// IMPORTANT: jest's fake timers are NOT used in this file. Test 1 and
// test 4 rely on real `setTimeout` wall-clock behavior, so we do not call
// `jest.useFakeTimers()` anywhere — the default is real timers and we
// leave it that way. (If you add helpers to this file later, do not
// switch to fake timers without re-reading this comment.)

jest.setTimeout(10_000);

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

test('benchmark1', async () => {
  // Sleep-dominated: ~2.15 s wall time.
  await sleep(2150);
});

test('benchmark2', () => {
  // Tight CPU loop, sub-millisecond. JavaScript engines can optimize
  // empty loops; touching `sink` keeps the body observable.
  let sink = 0;
  for (let i = 0; i < 1000; i++) {
    sink += i;
  }
  expect(sink).toBe(499500);
});

test('benchmark3', () => {
  // Allocate and fill 1.4 MB. Jest runs in Node, which has no direct
  // /dev/null write API worth using here; allocating and filling an
  // ArrayBuffer is the closest in-process analogue and exercises the
  // same I/O-shaped timing bucket as the bash reference.
  const N = 1_400_000;
  const buf = new Uint8Array(N);
  for (let i = 0; i < N; i++) {
    buf[i] = i & 0xff;
  }
  expect(buf.length).toBe(N);
});

test('benchmark4', async () => {
  // Monthly change-point showcase. sleep_s = 2.15 + ((m mod 3) - 1),
  // with m the current UTC month (1..12). See
  // docs/sample-benchmark.md test 4.
  const m = new Date().getUTCMonth() + 1; // getUTCMonth is 0-based
  const sleepS = 2.15 + ((m % 3) - 1);
  await sleep(Math.round(sleepS * 1000));
});
