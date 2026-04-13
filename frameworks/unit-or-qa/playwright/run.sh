#!/usr/bin/env bash
# Run the sample Playwright tests and emit the JSON report to ./output.json.
#
# The JSON reporter's output path is configured in playwright.config.ts
# (reporter: [['json', { outputFile: 'output.json' }]]), so `playwright
# test` writes ./output.json with no extra flags.
#
# `npx playwright install --with-deps chromium` fetches the chromium
# browser binary plus its Linux system dependencies. Even though these
# sample tests don't navigate to a page, Playwright still spins up the
# per-project worker machinery that expects the browser to be installable,
# and `--with-deps` is the documented way to install the required apt
# packages on CI runners.
set -euo pipefail

npm install
npx playwright install --with-deps chromium
npx playwright test
