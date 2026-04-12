#!/bin/bash
# Run the k6 sample-benchmark script and produce BOTH output formats
# that k6 supports:
#
#   - summary.json  — end-of-run summary (dict with top-level `metrics`
#                     and per-metric aggregate stats). Written by
#                     `--summary-export`.
#   - output.json   — streaming ndjson, one JSON object per data point
#                     (`type: "Point"`, `data: {time, value, tags}`,
#                     `metric: <name>`). Written by `--out json=...`.
#
# Both files are valuable as parser fixtures. The parser can choose
# which one to consume; we capture both so we never have to re-run CI
# to switch.
set -euo pipefail

cd "$(dirname "$0")"

k6 run \
    --summary-export=summary.json \
    --out json=output.json \
    sample-benchmark.js
