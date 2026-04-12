// tinybench implementation of the benchzoo canonical sample benchmark
// (see docs/sample-benchmark.md).
//
// tinybench (https://github.com/tinylibs/tinybench) is the modern JS
// micro-benchmark library that powers Vitest's `bench` mode. Here we
// use it directly — no Vitest — so the captured output is tinybench's
// own Task statistics, not wrapped in the Vitest JSON reporter shape.
//
// tinybench is a *library*, not a runner: there is no canonical output
// file format. This script defines the JSON shape it emits on stdout
// (see README.md "Parser notes"); run.sh redirects that to output.json.
//
// Sleep-dominated tests (1 and 4) are clamped to `iterations: 3` at the
// Bench level so the whole suite finishes in ~15 s rather than running
// for tinybench's default time budget against a 2-second callback.

import { Bench } from 'tinybench';

// iterations: 3 keeps sleepy tests bounded. Fast tests (2, 3) would
// prefer many more iterations for stable stats, but tinybench's
// iteration count is a per-Bench setting, not per-task — we accept
// three-iteration stats across the board in exchange for a short suite.
const bench = new Bench({ iterations: 3 });

// ---------------------------------------------------------------
// benchmark1 — sleep 2.15 s. Async callback; tinybench awaits it.
// ---------------------------------------------------------------
bench.add('benchmark1', async () => {
  await new Promise((r) => setTimeout(r, 2150));
});

// ---------------------------------------------------------------
// benchmark2 — tight loop 0..1000. Sum into a module-scoped sink so
// V8 cannot elide the loop as dead code.
// ---------------------------------------------------------------
let benchmark2Sink = 0;
bench.add('benchmark2', () => {
  let sum = 0;
  for (let i = 0; i < 1000; i++) sum += i;
  benchmark2Sink = sum;
});

// ---------------------------------------------------------------
// benchmark3 — "write 1.4 MB to /dev/null". tinybench is runtime-
// agnostic (Node, Deno, Bun, browser) so we do not touch the
// filesystem — we allocate a 1,400,000-byte ArrayBuffer and sparsely
// fill it. Same adaptation as vitest-bench and k6. Byte count
// preserved exactly so the ground-truth magnitude matches.
// ---------------------------------------------------------------
bench.add('benchmark3', () => {
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
bench.add('benchmark4', async () => {
  await new Promise((r) => setTimeout(r, benchmark4SleepMs));
});

await bench.run();

// Emit JSON on stdout; run.sh redirects to output.json.
// tinybench's Task.result carries the rich stats shape (mean, min,
// max, variance, sd, sem, df, critical, moe, rme, hz, period, p75,
// p99, p995, p999, samples[], totalTime). Spreading `t.result` copies
// them all verbatim — the parser is free to pick whichever fields it
// needs.
const out = {
  framework: 'tinybench',
  version: '3.0.6',
  month,
  results: bench.tasks.map((t) => ({ name: t.name, ...t.result })),
};
process.stdout.write(JSON.stringify(out, null, 2) + '\n');
