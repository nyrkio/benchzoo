#!/bin/bash
# Run the canonical sample benchmark under criterion and collect the
# per-bench `estimates.json` files into ./output/.
#
# criterion's native output is a directory tree under
# `target/criterion/<bench_name>/{new,base,change}/...`. The richest
# single file per bench is `new/estimates.json`, which holds the
# mean/median/std_dev/slope point estimates and their confidence
# intervals in nanoseconds. That's what we capture into `output/`.
#
# We also capture the "bencher" text format via `--output-format bencher`.
# This produces libtest-compatible lines like:
#   test benchmark1 ... bench: 2150000000 ns/iter (+/- 1234)
# The bencher format is lossy (median/std_dev only, integer-rounded, no
# confidence intervals) but it's a common real-world format — many CI
# setups parse it — and it's identical to `cargo bench` (libtest) output,
# so the parser can potentially be shared.
#
# The `output/` directory plus `output-bencher.txt` form the artifact
# shape the workflow uploads. The JSON files are named `benchmarkN.json`
# so the parser can key test_name off the filename if it prefers not to
# walk a directory tree.
set -euo pipefail

cd "$(dirname "$0")"

rm -rf output
mkdir -p output

# `cargo bench --bench sample_benchmark` runs every bench group declared
# in `criterion_main!`. With harness = false and no filter, all four
# benches execute. We tee stdout to output-text.txt to capture criterion's
# DEFAULT human-readable output (the "benchmarkN  time: [lo mid hi]" lines)
# — the format the `criterion_text` parser reads, distinct from the
# estimates.json and bencher fixtures below.
cargo bench --bench sample_benchmark 2>&1 | tee output-text.txt

# Copy the per-bench estimates.json files into ./output/ under a flat
# naming scheme. The `new/` subdirectory is the most recent run;
# criterion also writes `base/` from the previous run if one exists, and
# a `change/estimates.json` comparing the two — we intentionally only
# capture `new/` because benchzoo's fixture is a point-in-time snapshot,
# not a delta against CI history.
for name in benchmark1 benchmark2 benchmark3 benchmark4; do
    src="target/criterion/${name}/new/estimates.json"
    if [[ ! -f "${src}" ]]; then
        echo "ERROR: expected ${src} to exist after cargo bench" >&2
        exit 1
    fi
    cp "${src}" "output/${name}.json"
done

# Second run: capture the bencher text format. The `--output-format`
# flag is a criterion argument passed after `--` (not a cargo flag).
# criterion reuses cached measurements so this is fast.
cargo bench --bench sample_benchmark -- --output-format bencher > output-bencher.txt 2>&1

ls -la output/
echo "--- output-bencher.txt ---"
cat output-bencher.txt
