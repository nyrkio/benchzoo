#!/bin/bash
# Run all four canonical sample-benchmark tests under sysbench and
# concatenate the text output to ./output.txt. This is the command the
# workflow (and a local `act` run) execute; keeping it in a script
# rather than inline in the YAML makes it easy to iterate locally.
#
# sysbench runs exactly one Lua script per invocation, so we invoke it
# four times -- once per benchmarkN.lua -- and emit a
# `=== benchmarkN ===` separator before each block so the parser can
# split the concatenated output by test.
#
# --events=1 means event() is called exactly once per invocation. Total
# wall time is bounded by the slowest test (benchmark4 in February and
# August: ~3.15 s) -- worst-case around 6 seconds for the full run.
#
# --threads=1 keeps the "Threads fairness" block trivial; we only care
# about the "Latency" block for a single event.
set -euo pipefail

cd "$(dirname "$0")"

{
    for n in 1 2 3 4; do
        echo "=== benchmark${n} ==="
        sysbench ./benchmark${n}.lua --events=1 --threads=1 run
    done
} > output.txt 2>&1
