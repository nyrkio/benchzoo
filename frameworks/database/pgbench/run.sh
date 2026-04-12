#!/bin/bash
# Run all four canonical sample-benchmark tests under pgbench and
# concatenate the per-test output into ./output.txt. This is the command
# the workflow (and a local `act` run) execute; keeping it in a script
# rather than inline in the YAML makes it easy to iterate locally.
#
# pgbench is designed around repeated execution of a transaction against
# a running PostgreSQL server, so unlike hyperfine there is no single
# "run all four" invocation — we invoke pgbench four times, once per
# custom script, and stitch the outputs together with clear separators.
#
# Flags:
#   -f <script>  run the given SQL file as a custom transaction
#   -t 1         one transaction (the canonical suite measures a single
#                wall time per test, not a throughput sweep)
#   -c 1 -j 1    one client, one thread
#   -n           skip the initial VACUUM — we don't create pgbench's
#                standard tables so there's nothing to vacuum
#
# Connection parameters come from the PG* environment variables set by
# the workflow (PGHOST, PGPORT, PGUSER, PGDATABASE, PGPASSWORD).
set -euo pipefail

cd "$(dirname "$0")"

: > output.txt

for n in 1 2 3 4; do
    echo "=== benchmark${n} ===" >> output.txt
    pgbench \
        -f "benchmark${n}.sql" \
        -t 1 \
        -c 1 \
        -j 1 \
        -n \
        2>&1 | tee -a output.txt
    echo >> output.txt
done
