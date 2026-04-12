// benchmark.js implementation of the benchzoo canonical sample benchmark
// (see docs/sample-benchmark.md).
//
// benchmark.js is the classic Node/browser micro-benchmarking library
// (https://benchmarkjs.com/). It auto-calibrates the number of cycles
// per sample and collects multiple samples, producing per-benchmark
// statistics: hz (ops/sec), mean (seconds/op), rme (relative margin of
// error %), sample count, deviation, variance.
//
// NOTE — sleep handling via deferred mode:
//
// Tests 1 and 4 are dominated by a ~1-3 second sleep. A synchronous
// busy-wait would burn CPU for that entire duration and would be
// repeated by benchmark.js across many samples, making the suite take
// minutes instead of seconds. The natural fit is benchmark.js's
// *deferred* mode: declare `defer: true` and receive a `deferred` token
// whose `resolve()` call tells benchmark.js that one op has completed.
// We implement the sleep as `setTimeout(() => deferred.resolve(), ms)`.
// benchmark.js handles async completion cleanly in this mode and its
// reported `mean` is the wall time of one deferred op — which is what
// we want.
//
// Tests 2 and 3 are fast (sub-ms / low-ms) and synchronous, so we use
// the plain `fn` form — benchmark.js will run many iterations per
// sample and average.
//
// Output shape (emitted as JSON on stdout):
//
//   {
//     "framework": "benchmark.js",
//     "version": "2.1.4",
//     "results": [
//       {
//         "name": "benchmark1",
//         "hz": 0.4651,              // ops/sec
//         "mean": 2.150,             // seconds/op
//         "rme": 0.12,               // relative margin of error, %
//         "deviation": 0.001,        // stddev, seconds
//         "variance": 1e-6,          // seconds^2
//         "samples": 5,              // sample count
//         "cycles": 1,
//         "deferred": true,
//         "passed": true
//       },
//       ...
//     ]
//   }
//
// `hz` is benchmark.js's canonical throughput number (cycles/second of
// the measured op). `mean` is seconds per op — this is the field a
// parser should read for test 1's ground-truth ~2.15 s assertion.

const Benchmark = require('benchmark');
const fs = require('fs');

const suite = new Benchmark.Suite('benchzoo-canonical');

// ---------------------------------------------------------------
// benchmark1 — sleep 2.15 s (deferred / async).
// ---------------------------------------------------------------
suite.add('benchmark1', {
  defer: true,
  fn: function (deferred) {
    setTimeout(() => deferred.resolve(), 2150);
  },
  // Keep the suite fast: 5 samples * 2.15 s ~= 11 s is plenty.
  minSamples: 5,
  maxTime: 15,
});

// ---------------------------------------------------------------
// benchmark2 — tight CPU loop 0..1000. Synchronous. benchmark.js will
// run many iterations per sample; its `mean` will be sub-microsecond.
// `sum` is read after the loop so V8 cannot elide it.
// ---------------------------------------------------------------
let benchmark2Sink = 0;
suite.add('benchmark2', {
  fn: function () {
    let sum = 0;
    for (let i = 0; i < 1000; i++) sum += i;
    benchmark2Sink = sum;
  },
});

// ---------------------------------------------------------------
// benchmark3 — "write 1.4 MB to /dev/null". Node *does* have filesystem
// access, so we could literally fs.writeFileSync('/dev/null', buf) —
// and we do. We allocate the 1,400,000-byte buffer once outside the
// timed function so the measurement reflects the write, not the
// allocation. Fill with a deterministic pseudo-random pattern.
// ---------------------------------------------------------------
const benchmark3Buf = Buffer.alloc(1_400_000);
for (let i = 0; i < benchmark3Buf.length; i++) {
  benchmark3Buf[i] = (i * 2654435761) & 0xff; // Knuth multiplicative hash
}
suite.add('benchmark3', {
  fn: function () {
    fs.writeFileSync('/dev/null', benchmark3Buf);
  },
});

// ---------------------------------------------------------------
// benchmark4 — monthly change-point showcase. Sleep duration is
// 2.15 + ((UTC month mod 3) - 1) seconds; cycles through
// {1.15, 2.15, 3.15}. Deferred / async like benchmark1.
// ---------------------------------------------------------------
const benchmark4Month = new Date().getUTCMonth() + 1; // 1..12
const benchmark4SleepSec = 2.15 + ((benchmark4Month % 3) - 1);
const benchmark4SleepMs = Math.round(benchmark4SleepSec * 1000);
suite.add('benchmark4', {
  defer: true,
  fn: function (deferred) {
    setTimeout(() => deferred.resolve(), benchmark4SleepMs);
  },
  minSamples: 5,
  maxTime: 20,
});

// ---------------------------------------------------------------
// Collect per-benchmark results on cycle-complete. benchmark.js fires
// `cycle` once per benchmark (after all its samples are done), with
// `event.target` being the finished Benchmark instance.
// ---------------------------------------------------------------
const results = [];

suite.on('cycle', function (event) {
  const b = event.target;
  // b.stats: { moe, rme, sem, deviation, mean, variance, sample[] }
  // b.hz, b.cycles, b.count, b.times, b.error, b.aborted
  const entry = {
    name: b.name,
    hz: b.hz,                        // ops/sec
    mean: b.stats.mean,              // seconds/op
    rme: b.stats.rme,                // relative margin of error, %
    deviation: b.stats.deviation,    // stddev, seconds
    variance: b.stats.variance,      // seconds^2
    moe: b.stats.moe,                // margin of error, seconds
    sem: b.stats.sem,                // standard error of the mean, seconds
    samples: b.stats.sample.length,  // sample count
    cycles: b.cycles,
    deferred: Boolean(b.defer),
    passed: !b.error && !b.aborted,
  };
  if (b.error) {
    entry.error = String(b.error);
  }
  results.push(entry);
  // Human-readable line on stderr for live progress.
  console.error(String(event.target));
});

suite.on('complete', function () {
  const out = {
    framework: 'benchmark.js',
    version: Benchmark.version,
    month: benchmark4Month,
    results: results,
  };
  // JSON on stdout — run.sh redirects it to output.json.
  process.stdout.write(JSON.stringify(out, null, 2) + '\n');
});

suite.on('error', function (event) {
  console.error('benchmark error:', event.target.error);
});

// `async: true` keeps the event loop alive between deferred benchmarks
// so setTimeout-based tests work correctly.
suite.run({ async: true });
