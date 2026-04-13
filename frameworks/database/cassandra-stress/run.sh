#!/bin/bash
# Run the three cassandra-stress workloads (write, read, mixed) against a
# locally-reachable Cassandra node and capture each native text output as
# a separate file. Cassandra's startup is notoriously slow — the service
# container's own healthcheck is already generous, but we still guard the
# run with an explicit CQL-level wait loop so the first stress command
# doesn't race container readiness.
#
# Flags:
#   n=10000         10,000 operations per workload — keeps CI bounded
#   -rate threads=4 modest concurrency so the output has representative
#                   latency percentiles without saturating the small
#                   single-node service container
#   -node localhost point at the service container exposed on 9042
#
# Each workload writes its own output file so the parser can segment by
# test name (write / read / mixed) from the filename, matching the
# pgbench pattern of "one capture per test, concatenated by convention."
set -euo pipefail

cd "$(dirname "$0")"

echo "Waiting for Cassandra to accept CQL connections..."
deadline=$((SECONDS + 60))
until cqlsh localhost -e "SELECT now() FROM system.local" >/dev/null 2>&1; do
    if [ "$SECONDS" -ge "$deadline" ]; then
        echo "Timed out after 60s waiting for Cassandra" >&2
        exit 1
    fi
    sleep 2
done
echo "Cassandra is ready."

cassandra-stress write n=10000 -rate threads=4 -node localhost > output-write.txt 2>&1
cassandra-stress read  n=10000 -rate threads=4 -node localhost > output-read.txt  2>&1
cassandra-stress mixed ratio\(write=1,read=1\) n=10000 -rate threads=4 -node localhost > output-mixed.txt 2>&1
