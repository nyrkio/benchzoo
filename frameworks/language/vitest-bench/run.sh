#!/bin/bash
# Run vitest's bench mode against the canonical sample-benchmark file and
# write the JSON report to ./output.json.
#
# Vitest's JSON reporter produces a single top-level object. In bench mode
# each `bench(...)` call appears as a `testResults[].assertionResults[]`
# entry, and the tinybench stats (mean, min, max, p75, p99, hz, rme,
# samples) are attached per assertion. See README.md for schema notes.
set -euo pipefail

cd "$(dirname "$0")"

npm install
# NOTE: vitest bench mode only supports the "default" and "verbose"
# reporters — the "json" string is interpreted as a path to a reporter
# module and fails with "Failed to load url json". To capture JSON,
# we use the --outputJson flag (supported since vitest 1.x) which
# writes the raw bench results separately from the reporter.
npx vitest bench --run --outputJson=output.json
