// Canonical sample benchmark expressed as four Playwright tests.
//
// Playwright is a browser-automation-focused end-to-end test runner, but
// at its core it is still a test runner that records per-test wall time
// in its JSON report — exactly the "unit test runner as timing source"
// pattern from docs/parser-targets.md section 6.
//
// These tests do NOT navigate to a page. The canonical sample benchmark
// is a sleep / CPU loop / buffer allocation / month-based sleep — none
// of which are browser-y. Rather than shoehorn a `page.goto('about:blank')`
// into each test for no reason, we just run the work directly in the
// test body. See the README for the full adaptation rationale.
//
// Each test(name, ...) name maps directly to the identifier the parser
// will write into attributes["test_name"].
import { test, expect } from '@playwright/test';

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

test('benchmark1', async () => {
  // Sleep-dominated: ~2.15 s wall time.
  await sleep(2150);
});

test('benchmark2', () => {
  // Tight CPU loop, sub-millisecond. Touching `sink` keeps a clever JS
  // engine from eliding the loop body, analogous to std::hint::black_box
  // in Rust or Blackhole.consume in JMH.
  let sink = 0;
  for (let i = 0; i < 1000; i++) {
    sink += i;
  }
  expect(sink).toBe(499500);
});

test('benchmark3', () => {
  // Allocate and fill 1.4 MB. Node has no ergonomic /dev/null write API;
  // filling an ArrayBuffer is the closest in-process analogue and
  // exercises the same I/O-shaped timing bucket as the bash reference.
  const N = 1_400_000;
  const buf = new Uint8Array(N);
  for (let i = 0; i < N; i++) {
    buf[i] = i & 0xff;
  }
  expect(buf.length).toBe(N);
});

test('benchmark4', async () => {
  // Monthly change-point showcase. sleep_s = 2.15 + ((m mod 3) - 1),
  // with m the current UTC month (1..12). See docs/sample-benchmark.md
  // test 4.
  const m = new Date().getUTCMonth() + 1; // getUTCMonth is 0-based
  const sleepS = 2.15 + ((m % 3) - 1);
  await sleep(Math.round(sleepS * 1000));
});
