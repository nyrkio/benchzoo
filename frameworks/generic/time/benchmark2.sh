#!/bin/bash
# benchmark2 — tight CPU loop, sub-millisecond in scripting languages.
# An empty for loop counting 0..1000 in bash. Bash is interpreted, so
# the loop is not optimized away — no black_box needed.
# See ../../../docs/sample-benchmark.md for the canonical spec.
set -euo pipefail
echo "Starting benchmark2"
for ((i=0; i<1000; i++)); do :; done
echo "End of benchmark2"
