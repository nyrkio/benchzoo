// Minimal Playwright config for the benchzoo sample benchmark.
//
// We are using Playwright purely as a test runner here — the tests don't
// navigate to any real page. See tests/sample.spec.ts and the README for
// the rationale. The config therefore only needs:
//
//   - the JSON reporter (the parser target for this framework), with a
//     stable output path so run.sh / CI can pick it up,
//   - a single "chromium" project entry, because Playwright requires at
//     least one project even if no browser navigation happens. Restricting
//     to chromium also means `npx playwright install` only has to fetch
//     one browser binary in CI.
//   - a per-test timeout generous enough for test 1 / test 4 (up to
//     3.15 s of sleep) without being so large it hides hangs.
import { defineConfig } from '@playwright/test';

export default defineConfig({
  reporter: [['json', { outputFile: 'output.json' }]],
  timeout: 10000,
  projects: [
    {
      name: 'chromium',
      use: {},
    },
  ],
});
