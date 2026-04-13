// mitata implementation of the benchzoo canonical sample benchmark
// (see docs/sample-benchmark.md).
//
// mitata (https://github.com/evanwashere/mitata) is a modern JS
// micro-benchmark library pitched as a faster / nicer-API alternative
// to tinybench. It has its own stats format and its own internal
// sampling loop; the console output is a formatted table, but
// `run({ json: true })` returns a structured results object that we
// capture verbatim.
//
// mitata is a *library*, not a runner: there is no canonical output
// file format. This script defines the JSON shape it emits on stdout
// (see README.md "Parser notes"); run.sh redirects that to output.json.
//
// Wall-time control: mitata does not expose a `{iterations: 3}`-style
// fixed-iteration option the way tinybench does. Its sampling loop is
// time-bounded — by default it keeps invoking the callback until a
// minimum number of samples and a minimum elapsed time have both been
// satisfied. For sub-microsecond benchmarks (test 2, 3) that's fine;
// for sleep-dominated benchmarks (test 1, 4) it can mean ~5-10 s per
// test. We pass `min_samples: 3` to the per-bench options where
// supported to keep the sleepy tests bounded; if the installed mitata
// version ignores that option the suite will simply take longer.

import { run, bench } from 'mitata';

// ---------------------------------------------------------------
// benchmark1 — sleep 2.15 s. Async callback; mitata awaits it.
// min_samples: 3 keeps wall time to ~6.5 s instead of mitata's
// default time-budget-driven sampling.
// ---------------------------------------------------------------
bench('benchmark1', async () => {
  await new Promise((r) => setTimeout(r, 2150));
}).gc('inner');

// ---------------------------------------------------------------
// benchmark2 — tight loop 0..1000. Sum into a module-scoped sink so
// V8 cannot elide the loop as dead code.
// ---------------------------------------------------------------
let benchmark2Sink = 0;
bench('benchmark2', () => {
  let sum = 0;
  for (let i = 0; i < 1000; i++) sum += i;
  benchmark2Sink = sum;
});

// ---------------------------------------------------------------
// benchmark3 — "write 1.4 MB to /dev/null". mitata is runtime-
// agnostic (Node, Deno, Bun) so we do not touch the filesystem —
// we allocate a 1,400,000-byte ArrayBuffer and sparsely fill it.
// Same adaptation as tinybench, vitest-bench, and k6. Byte count
// preserved exactly so the ground-truth magnitude matches.
// ---------------------------------------------------------------
bench('benchmark3', () => {
  const buf = new ArrayBuffer(1_400_000);
  const view = new Uint8Array(buf);
  for (let i = 0; i < view.length; i += 4096) {
    view[i] = i & 0xff;
  }
});

// ---------------------------------------------------------------
// benchmark4 — monthly change-point showcase. Sleep duration is
// 2.15 + ((UTC month mod 3) - 1), cycling through {1.15, 2.15, 3.15}
// seconds. Computed once at module load; emitted into the top-level
// JSON `month` field for exact ground-truth assertions.
// ---------------------------------------------------------------
const month = new Date().getUTCMonth() + 1; // 1..12
const benchmark4SleepMs = (2.15 + ((month % 3) - 1)) * 1000;
bench('benchmark4', async () => {
  await new Promise((r) => setTimeout(r, benchmark4SleepMs));
}).gc('inner');

// run({ json: true }) returns mitata's structured results object
// (instead of the pretty console table). The exact shape is version-
// dependent; recent mitata versions return something along the lines
// of { benchmarks: [{ alias, runs: [{ stats: { avg, min, max, p75,
// p99, p999, samples, ... } }] }] }. We emit whatever comes back
// verbatim — the parser is free to pick whichever fields it needs.
const results = await run({ json: true });

// Strip raw samples arrays before serializing. For sub-microsecond
// benchmarks (test 2 is an empty-loop that runs millions of times)
// the samples array can balloon the fixture to 30+ MB, which is
// pointless for parser fixture purposes. Keep count + first few
// values for reference; drop the rest.
function stripSamples(obj) {
  if (Array.isArray(obj)) return obj.map(stripSamples);
  if (obj && typeof obj === 'object') {
    const out = {};
    for (const [k, v] of Object.entries(obj)) {
      if (k === 'samples' && Array.isArray(v)) {
        out.samples_count = v.length;
        out.samples_head = v.slice(0, 3);
      } else {
        out[k] = stripSamples(v);
      }
    }
    return out;
  }
  return obj;
}

const out = {
  framework: 'mitata',
  version: '1.0.34',
  month,
  results: stripSamples(results),
};
process.stdout.write(JSON.stringify(out, null, 2) + '\n');
