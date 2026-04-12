#!/bin/bash
# benchmark4 — monthly change-point showcase.
# Sleep duration = 2.15 + ((m mod 3) - 1) where m is the current UTC month.
# Produces a deterministic {1.15, 2.15, 3.15} cycle with period 3 months,
# so a full year has 11 change points for downstream change-detection
# tooling to verify against. See ../../../docs/sample-benchmark.md.
set -euo pipefail
echo "Starting benchmark4"
m=$(date -u +%-m)                                       # 1..12, UTC, no leading zero
sleep_s=$(awk "BEGIN { print 2.15 + ($m % 3) - 1 }")    # bash can't do float math
echo "benchmark4: month=$m, sleep=${sleep_s}s"
sleep "${sleep_s}"
echo "End of benchmark4"
