#!/bin/bash
# Run YCSB against the workflow's Redis service container in two
# phases:
#
#   1. `load` — populate the database with `recordcount` rows. YCSB
#      emits its own stats block for the load phase (INSERT
#      throughput / latency). Captured to output-load.txt.
#
#   2. `run`  — replay `operationcount` operations against the loaded
#      data, in the read/update mix declared in workload.txt. YCSB
#      emits stats blocks for READ and UPDATE. Captured to
#      output-run.txt.
#
# Both phases are run with `-s` (status lines to stderr every 10s)
# merged into the output file — the summary block at the end is what
# the parser consumes. The `redis` binding ships inside the
# `ycsb-redis-binding-0.17.0.tar.gz` tarball the workflow downloads.
set -euo pipefail

cd "$(dirname "$0")"

./ycsb-0.17.0/bin/ycsb load redis -s -P workload.txt \
    -p redis.host=localhost -p redis.port=6379 \
    > output-load.txt 2>&1

./ycsb-0.17.0/bin/ycsb run redis -s -P workload.txt \
    -p redis.host=localhost -p redis.port=6379 \
    > output-run.txt 2>&1
