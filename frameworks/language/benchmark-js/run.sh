#!/bin/bash
# Run the benchmark.js sample-benchmark suite and capture its JSON
# output.
#
# benchmark.js is a library, not a runner — there is no standard output
# format. `sample-benchmark.js` itself defines the JSON shape it emits
# on stdout (see that file's header comment, and Parser notes in
# README.md). This script just installs deps and redirects stdout to
# output.json.
#
# stderr carries benchmark.js's human-readable per-cycle lines and any
# npm noise. We merge it into output.json too (`2>&1` after the stdout
# redirect would destroy the JSON; instead we append stderr to a
# separate log). Keep them apart: output.json must be valid JSON.
set -euo pipefail

cd "$(dirname "$0")"

npm install --no-audit --no-fund

node sample-benchmark.js > output.json 2> output.log
