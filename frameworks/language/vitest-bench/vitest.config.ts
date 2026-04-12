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
      // Bench mode reporters are limited to "default" and "verbose" —
      // "json" is not available here (it is a test-mode-only reporter).
      // To capture JSON we pass --outputJson=output.json on the CLI,
      // which is a separate flag independent of the reporter.
      reporters: ['default'],
    },
  },
});
