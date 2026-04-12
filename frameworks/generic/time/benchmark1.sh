#!/bin/bash
# benchmark1 — sleep-dominated (~2.15 s).
# See ../../../docs/sample-benchmark.md for the canonical spec.
set -euo pipefail
echo "Starting benchmark1"
sleep 2.15
echo "End of benchmark1"
