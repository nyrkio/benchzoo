#!/bin/bash
# benchmark3 — write exactly 1,400,000 bytes of /dev/urandom to /dev/null.
# Decimal MB (1.4 MB = 1_400_000 bytes), not binary MiB — see the size
# convention note in ../../../docs/sample-benchmark.md.
set -euo pipefail
echo "Starting benchmark3"
head -c 1400000 /dev/urandom > /dev/null
echo "End of benchmark3"
