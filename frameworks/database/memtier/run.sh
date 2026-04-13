#!/bin/bash
# Run memtier_benchmark against the workflow's Redis service container and
# capture both the JSON output (via --json-out-file) and the default
# human-readable text output (captured from stdout via tee).
#
# Like redis-benchmark, memtier_benchmark is not a "run four tests
# separately" tool — a single invocation drives a mix of SET and GET
# operations against the server and reports per-operation-type and
# overall statistics. The canonical sample-benchmark shape (tests 1-4)
# does not map cleanly onto this: memtier measures high-QPS operation
# latency distributions against a key/value service, not 2.15-second
# sleeps or 1.4 MB writes. We therefore adopt a looser interpretation:
# one run, and each operation type becomes a `test_name`
# (Sets, Gets, Totals). The README documents this deviation.
#
# Flags:
#   -s / -p             host and port of the Redis server
#   --protocol redis    use the Redis wire protocol (also supports memcached)
#   --test-time=5       run for 5 seconds (instead of a fixed request count)
#   --ratio=1:1         1 SET per 1 GET
#   --data-size=64      64-byte values
#   --clients=10        10 clients per thread
#   --threads=2         2 worker threads
#   --pipeline=1        no pipelining
#   --json-out-file     also emit structured JSON alongside the text output
set -euo pipefail

cd "$(dirname "$0")"

memtier_benchmark -s localhost -p 6379 --protocol redis \
    --test-time=5 --ratio=1:1 --data-size=64 \
    --clients=10 --threads=2 --pipeline=1 \
    --json-out-file=output.json 2>&1 | tee output.txt
