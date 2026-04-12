import { defineConfig } from 'vitest/config';

// Minimal config. Vitest's bench mode is triggered by `vitest bench` on the
// CLI and by `bench(...)` calls inside files matching the default
// `*.bench.{ts,js}` pattern. We keep per-benchmark iteration counts small
// because three of our four canonical tests are sleep-dominated — the
// tinybench default (hundreds of iterations until time budget is hit) would
// make test 1 and test 4 take minutes of wall time for no added signal.
export default defineConfig({
  test: {
    benchmark: {
      // Write the bench JSON report to ./output.json. The CLI flag
      // `--outputFile=output.json` does the same thing; we set it here too
      // so `npx vitest bench --run --reporter=json` produces the file even
      // when the caller forgets the flag.
      outputFile: 'output.json',
      reporters: ['default'],
    },
  },
});
