#!/bin/bash
# Run all four canonical sample-benchmark tests under hyperfine and
# write the JSON export to ./output.json. This is the command the
# workflow (and a local `act` run) execute; keeping it in a script
# rather than inline in the YAML makes it easy to iterate locally.
#
# hyperfine supports multiple commands in a single invocation and
# preserves their order in --export-json. We name each one so the
# parser can key off `results[i].command`.
#
# --warmup 1 gives the OS page cache a chance to stabilize before the
# timed runs. --runs 10 is the hyperfine default; we state it
# explicitly so changes are visible in PR diffs.
set -euo pipefail

cd "$(dirname "$0")"
chmod +x benchmark1.sh benchmark2.sh benchmark3.sh benchmark4.sh

hyperfine \
    --warmup 1 \
    --runs 10 \
    --export-json output.json \
    --export-csv output.csv \
    --export-markdown output.md \
    --command-name benchmark1 './benchmark1.sh' \
    --command-name benchmark2 './benchmark2.sh' \
    --command-name benchmark3 './benchmark3.sh' \
    --command-name benchmark4 './benchmark4.sh'
