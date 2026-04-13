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

# The redis-binding tarball extracts to
# ``ycsb-redis-binding-0.17.0/``, not ``ycsb-0.17.0/`` as the
# unspecialised distribution does. Resolve dynamically so the run
# script survives naming-convention churn between YCSB binding
# tarballs.
YCSB_DIR=$(ls -d ycsb-*-0.17.0 ycsb-0.17.0 2>/dev/null | head -n 1)
if [[ -z "${YCSB_DIR}" ]]; then
    echo "ERROR: could not find extracted YCSB directory" >&2
    ls -la >&2
    exit 1
fi

"${YCSB_DIR}/bin/ycsb" load redis -s -P workload.txt \
    -p redis.host=localhost -p redis.port=6379 \
    > output-load.txt 2>&1

"${YCSB_DIR}/bin/ycsb" run redis -s -P workload.txt \
    -p redis.host=localhost -p redis.port=6379 \
    > output-run.txt 2>&1
