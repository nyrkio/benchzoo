#!/bin/bash
# Run each query in queries.sql three times, measure wall-clock latency
# of each run, and emit an output.json matching the ClickBench result
# format documented at
# https://github.com/ClickHouse/ClickBench/tree/main/clickhouse —
# { system, date, machine, cluster_size, comment, tags, load_time,
#   data_size, result: [[q1_r1, q1_r2, q1_r3], [q2_r1, ...], ...] }.
set -euo pipefail
cd "$(dirname "$0")"

: "${CLICKHOUSE_HOST:=localhost}"
CH="clickhouse-client --host=${CLICKHOUSE_HOST} --time"

# Time the data load so we can populate `load_time` in the JSON.
LOAD_START=$(date +%s.%N)
./load.sh > /dev/null
LOAD_END=$(date +%s.%N)
LOAD_TIME=$(awk "BEGIN { print ${LOAD_END} - ${LOAD_START} }")

DATA_SIZE=$(clickhouse-client --host="${CLICKHOUSE_HOST}" \
    --query="SELECT sum(bytes_on_disk) FROM system.parts WHERE table='hits' AND active")

# Collect each query's three run times into a JSON-encoded sub-array.
RESULT_ARRAYS=()
while IFS= read -r query; do
    # Skip blank lines and SQL comments.
    [[ -z "$query" || "$query" =~ ^-- ]] && continue
    RUNS=()
    for _ in 1 2 3; do
        T_START=$(date +%s.%N)
        clickhouse-client --host="${CLICKHOUSE_HOST}" --query="$query" > /dev/null
        T_END=$(date +%s.%N)
        RUNS+=("$(awk "BEGIN { print ${T_END} - ${T_START} }")")
    done
    RESULT_ARRAYS+=("[$(IFS=,; echo "${RUNS[*]}")]")
done < queries.sql

RESULT_JSON="[$(IFS=,; echo "${RESULT_ARRAYS[*]}")]"
DATE=$(date -u +%Y-%m-%d)

cat > output.json <<EOF
{
  "system": "ClickHouse",
  "date": "${DATE}",
  "machine": "github-actions-ubuntu-latest",
  "cluster_size": 1,
  "comment": "benchzoo fixture — synthetic 10k-row dataset, 5 of 43 queries",
  "tags": ["column-oriented", "OLAP", "benchzoo-fixture"],
  "load_time": ${LOAD_TIME},
  "data_size": ${DATA_SIZE},
  "result": ${RESULT_JSON}
}
EOF

cat output.json
