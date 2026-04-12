#!/bin/bash
# Build the JMH sample-benchmark uberjar and run it, emitting three
# output formats: JSON (primary fixture), CSV (compact tabular), and
# rich text (captured via stdout redirect).
#
# JMH only writes one -rf format per invocation, so we run the suite
# twice: once for JSON and once for CSV. The text output is captured
# from stdout of the first run via tee.
#
# JMH flags:
#   -rf  json|csv         — result format
#   -rff output.json|csv  — result file
#
# Note on CI wall time: the sleep-heavy benchmark1 and benchmark4 each
# take ~6.5 s per measurement iteration × 3 iterations × 1 fork, plus a
# warmup iteration. Expect total suite runtime on the order of a minute
# on a GitHub-hosted runner; a bit longer under `act` in local Docker.
set -euo pipefail

cd "$(dirname "$0")"

mvn -q package

java -jar target/benchmarks.jar \
    -rf json \
    -rff output.json \
    | tee output.txt

# Second invocation: produce the CSV result format.
# JMH only writes one -rf per invocation, so we re-run with -rf csv.
# The benchmark suite is fast enough that the extra run is acceptable.
java -jar target/benchmarks.jar \
    -rf csv \
    -rff output.csv \
    > /dev/null
