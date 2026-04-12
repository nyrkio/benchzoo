#!/bin/bash
# emit.sh — generate an exemplar fixture for the generic CSV escape-hatch
# format.
#
# This is NOT the output of a real benchmarking tool. It's a file format
# defined by benchzoo itself (inherited from nyrkio/change-detection) as
# an escape hatch for users whose tooling doesn't match any of the
# framework-specific parsers. If you can get your numbers into this CSV,
# you can get them into benchzoo.
#
# Format (see docs/parser-targets.md §7a):
#
#   Header row:  test_name,metric_name,unit,value,direction
#   One row per (test, metric) pair.
#
#   - test_name   — arbitrary string; becomes attributes["test_name"]
#   - metric_name — arbitrary string; becomes metrics[i]["name"]
#   - unit        — arbitrary string; becomes metrics[i]["unit"] verbatim
#   - value       — number parsed as float; becomes metrics[i]["value"]
#   - direction   — "higher_is_better" | "lower_is_better" | "" (omit)
#
# Multiple rows sharing the same test_name are grouped into a single
# Nyrkiö dict with multiple entries in its metrics[] array. This is how
# the CSV escape hatch differs from the JSON escape hatch: the CSV
# supports per-test statistics (mean, min, max, stddev, p99) natively,
# while the JSON format has one metric per entry.
#
# Because this is an exemplar fixture rather than a real measurement,
# the values are the canonical sample-benchmark ground truths
# (docs/sample-benchmark.md). Test 4's value follows the same monthly
# formula as hyperfine's benchmark4.sh.
set -euo pipefail

cd "$(dirname "$0")"

# Test 4 sleep duration, computed the same way benchmark4.sh does it
# across every framework: 2.15 + ((m mod 3) - 1) with m = current UTC month.
m=$(date -u +%-m)
t4_seconds=$(awk "BEGIN { printf \"%.2f\", 2.15 + ($m % 3) - 1 }")

cat > output.csv <<EOF
test_name,metric_name,unit,value,direction
benchmark1,mean,s,2.15,lower_is_better
benchmark1,min,s,2.14,lower_is_better
benchmark1,max,s,2.16,lower_is_better
benchmark1,stddev,s,0.01,lower_is_better
benchmark2,mean,us,50,lower_is_better
benchmark2,min,us,45,lower_is_better
benchmark2,max,us,58,lower_is_better
benchmark3,mean,ms,1.0,lower_is_better
benchmark3,min,ms,0.9,lower_is_better
benchmark3,max,ms,1.2,lower_is_better
benchmark3,throughput,MB/s,1400,higher_is_better
benchmark4,mean,s,${t4_seconds},lower_is_better
benchmark4,month,,${m},
EOF

echo "Wrote output.csv"
