#!/bin/bash
# Run redis-benchmark against the workflow's Redis service container and
# capture both the CSV and the default human-readable text output.
#
# Unlike pgbench, redis-benchmark is not a "run four tests separately"
# tool — a single invocation iterates over several built-in command
# types (SET, GET, INCR, LPUSH, RPUSH, MSET, …) and emits one summary
# row per command. The canonical sample-benchmark shape (tests 1-4)
# does not map cleanly onto this: redis-benchmark measures high-QPS
# command latency distributions, not 2.15-second sleeps or 1.4 MB
# writes. We therefore adopt a looser interpretation: one run, and
# each command type becomes a `test_name` (SET, GET, INCR, …). The
# README documents this deviation.
#
# We select a small subset of command types via `-t` to keep the CI
# run bounded:
#     set, get, incr, lpush, rpush, mset
#
# Flags:
#   -h / -p           host and port of the Redis server
#   -t <list>         comma-separated list of command types to run
#   -n 100000         total number of requests per command type
#   -c 50             50 parallel clients
#   --csv             emit CSV (one header row + one row per command)
#
# Two invocations — one per output format — because redis-benchmark
# cannot emit both CSV and its default text summary in a single run.
set -euo pipefail

cd "$(dirname "$0")"

redis-benchmark -h localhost -p 6379 -t set,get,incr,lpush,rpush,mset \
    -n 100000 -c 50 --csv > output.csv 2>&1

redis-benchmark -h localhost -p 6379 -t set,get,incr,lpush,rpush,mset \
    -n 100000 -c 50 > output.txt 2>&1
