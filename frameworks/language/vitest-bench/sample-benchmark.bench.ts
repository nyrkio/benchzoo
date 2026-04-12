// Vitest `bench` implementation of the benchzoo canonical sample benchmark
// (see docs/sample-benchmark.md).
//
// Vitest bench mode is built on top of tinybench. Each `bench(name, fn)`
// runs `fn` many times and records a distribution (mean, min, max, p75,
// p99, hz, rme, samples). Async callbacks are awaited. We clamp the
// sleep-dominated tests (1 and 4) to a small number of iterations via
// `{ iterations: 3, warmupIterations: 0, time: 0 }` so the workflow
// finishes in seconds rather than minutes.

import { bench, describe } from 'vitest';

// Short-iteration option set for sleep-dominated tests. `time: 0` tells
// tinybench to stop as soon as `iterations` is hit (otherwise it keeps
// running until the minimum time budget elapses, which would be ~10 s).
const SLEEPY = { iterations: 3, warmupIterations: 0, time: 0, warmupTime: 0 };

describe('benchzoo canonical sample benchmark', () => {
  // -----------------------------------------------------------------
  // benchmark1 — sleep 2.15 s. Async bench callback; vitest awaits it.
  // Three iterations so the parser sees a distribution with stddev,
  // not a single point, while keeping wall time bounded.
  // -----------------------------------------------------------------
  bench(
    'benchmark1',
    async () => {
      await new Promise((resolve) => setTimeout(resolve, 2150));
    },
    SLEEPY,
  );

  // -----------------------------------------------------------------
  // benchmark2 — tight loop 0..1000. Accumulate into a sink so
  // V8 cannot elide the loop as dead code. Let tinybench run this
  // as many times as it likes (default time budget, ~500 ms) — it's
  // sub-microsecond, so hundreds of iterations is exactly what we
  // want for stable stats.
  // -----------------------------------------------------------------
  let sum = 0;
  bench('benchmark2', () => {
    for (let i = 0; i < 1000; i++) sum += i;
    // Touch `sum` so the loop is observably side-effecting.
    if (sum < 0) throw new Error('unreachable');
  });

  // -----------------------------------------------------------------
  // benchmark3 — "write 1.4 MB to /dev/null". Vitest benches run
  // inside a Node worker; we could write to /dev/null with `fs`, but
  // that's OS-specific and not portable. Follow the k6 convention:
  // allocate a 1,400,000-byte ArrayBuffer and sparsely fill it. The
  // measurement is "allocate + touch 1.4 MB of memory", not disk I/O.
  // Byte count is preserved so the ground-truth magnitude matches.
  // -----------------------------------------------------------------
  bench('benchmark3', () => {
    const buf = new ArrayBuffer(1_400_000);
    const view = new Uint8Array(buf);
    for (let i = 0; i < view.length; i += 4096) {
      view[i] = i & 0xff;
    }
  });

  // -----------------------------------------------------------------
  // benchmark4 — monthly change-point showcase. Sleep duration is
  // 2.15 + ((UTC month mod 3) - 1), so the series cycles through
  // {1.15, 2.15, 3.15} seconds with period 3 months. See test 4 in
  // docs/sample-benchmark.md.
  // -----------------------------------------------------------------
  const m = new Date().getUTCMonth() + 1; // 1..12
  const sleepMs = (2.15 + ((m % 3) - 1)) * 1000;
  bench(
    'benchmark4',
    async () => {
      await new Promise((resolve) => setTimeout(resolve, sleepMs));
    },
    SLEEPY,
  );
});
