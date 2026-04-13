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

# Probe for the extracted YCSB directory. The redis-binding tarball
# extracts to ycsb-redis-binding-0.17.0/ or similar; actual path
# varies by release, so we glob rather than hardcode. Fall back to
# listing all ycsb-* dirs.
echo "--- run.sh working dir contents ---" >&2
ls -la >&2 || true
YCSB_DIR=$({ ls -d ycsb-*/ 2>/dev/null || true; } | head -n 1 | sed 's:/*$::')
echo "--- chose YCSB_DIR=${YCSB_DIR} ---" >&2
if [[ -z "${YCSB_DIR}" ]] || [[ ! -x "${YCSB_DIR}/bin/ycsb" ]]; then
    echo "ERROR: no ycsb binary found at ${YCSB_DIR}/bin/ycsb" >&2
    exit 1
fi

# Tee output so it ends up in both the captured fixture AND the CI
# job log, making diagnosis easier when the benchmark fails.
"${YCSB_DIR}/bin/ycsb" load redis -s -P workload.txt \
    -p redis.host=localhost -p redis.port=6379 2>&1 | tee output-load.txt

"${YCSB_DIR}/bin/ycsb" run redis -s -P workload.txt \
    -p redis.host=localhost -p redis.port=6379 2>&1 | tee output-run.txt
