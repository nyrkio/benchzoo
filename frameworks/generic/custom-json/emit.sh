#!/bin/bash
# emit.sh — generate exemplar fixtures for the customBiggerIsBetter and
# customSmallerIsBetter JSON escape-hatch formats.
#
# These are NOT the output of a real benchmarking tool. They are file
# formats defined by benchzoo itself (inherited from nyrkio/change-detection,
# which in turn inherited the shape from benchmark-action/github-action-benchmark):
# a flat JSON array of {name, unit, value, extra?} objects.
#
# Format semantics — see docs/parser-targets.md §7a:
#
#   customBiggerIsBetter  — every `value` is a higher-is-better quantity
#                           (throughput, ops/s, score). The parser must emit
#                           `direction: "higher_is_better"` for every metric.
#
#   customSmallerIsBetter — every `value` is a lower-is-better quantity
#                           (latency, wall time, memory). The parser must
#                           emit `direction: "lower_is_better"` for every
#                           metric.
#
# `unit` is carried verbatim from the input to the Nyrkiö `unit` field —
# the parser does not interpret or normalize it.
#
# `name` in the input is used as BOTH the Nyrkiö `attributes["test_name"]`
# AND the metric `name`, because the custom format has only one metric per
# entry. Parsers produce one Nyrkiö dict per array entry, each with a
# single-element `metrics` array.
#
# `extra` is free-form and should be stashed in `extra_info` if present.
#
# Because these are exemplar fixtures, the values are the canonical
# sample-benchmark ground truths (docs/sample-benchmark.md). Test 4's
# sleep duration follows the same monthly formula as hyperfine's
# benchmark4.sh so the file regenerates deterministically per UTC month.
set -euo pipefail

cd "$(dirname "$0")"

# Test 4 sleep duration, computed the same way benchmark4.sh does it
# across every framework: 2.15 + ((m mod 3) - 1) with m = current UTC month.
m=$(date -u +%-m)
t4_seconds=$(awk "BEGIN { printf \"%.2f\", 2.15 + ($m % 3) - 1 }")

# customSmallerIsBetter: latency-flavored values (wall time in seconds).
# Every entry is a duration — smaller is better.
#
#   benchmark1 — 2.15 s sleep (ground truth exact)
#   benchmark2 — sub-millisecond tight CPU loop, call it 50 us
#   benchmark3 — ~1 ms for 1.4 MB of /dev/urandom to /dev/null
#   benchmark4 — month-derived sleep duration
cat > output-smaller.json <<EOF
[
  {
    "name": "benchmark1",
    "unit": "s",
    "value": 2.15,
    "extra": "sleep-dominated; canonical 2.15 s wall time"
  },
  {
    "name": "benchmark2",
    "unit": "us",
    "value": 50,
    "extra": "tight CPU loop, 0..1000"
  },
  {
    "name": "benchmark3",
    "unit": "ms",
    "value": 1.0,
    "extra": "write 1.4 MB of /dev/urandom to /dev/null"
  },
  {
    "name": "benchmark4",
    "unit": "s",
    "value": ${t4_seconds},
    "extra": "monthly change-point showcase; month=${m} UTC"
  }
]
EOF

# customBiggerIsBetter: throughput-flavored values (ops/s, score).
# Every entry is a rate — bigger is better. The values are chosen to be
# the "reciprocal-ish" reinterpretation of the same four tests so both
# files stay recognizable as the canonical suite, not to be physically
# meaningful.
#
#   benchmark1 — ~0.465 runs/s (one 2.15 s sleep per run)
#   benchmark2 — 20000 ops/s (reciprocal of 50 us)
#   benchmark3 — 1400 MB/s nominal throughput for the 1.4 MB write
#   benchmark4 — month-derived, 1/t4_seconds runs/s
t4_rate=$(awk "BEGIN { printf \"%.4f\", 1 / ${t4_seconds} }")
cat > output-bigger.json <<EOF
[
  {
    "name": "benchmark1",
    "unit": "runs/s",
    "value": 0.4651,
    "extra": "1 run per 2.15 s canonical sleep"
  },
  {
    "name": "benchmark2",
    "unit": "ops/s",
    "value": 20000,
    "extra": "tight CPU loop throughput"
  },
  {
    "name": "benchmark3",
    "unit": "MB/s",
    "value": 1400,
    "extra": "1.4 MB write to /dev/null in ~1 ms"
  },
  {
    "name": "benchmark4",
    "unit": "runs/s",
    "value": ${t4_rate},
    "extra": "monthly change-point showcase; month=${m} UTC"
  }
]
EOF

echo "Wrote output-smaller.json and output-bigger.json"
