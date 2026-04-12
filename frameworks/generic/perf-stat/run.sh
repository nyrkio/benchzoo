#!/bin/bash
# Run all four canonical sample-benchmark tests under Linux `perf stat`
# and capture the counter output in both formats perf natively supports:
#
#   1. default human-readable text format  -> output-text.txt
#   2. machine-readable CSV via `-x,`      -> output-csv.txt
#
# Both are worth capturing as fixtures because real users in the wild
# pipe perf output into whichever format their tooling expects. The
# default text is what shows up in blog posts and bug reports; the
# CSV is what scripts consume. They are different enough in shape
# that downstream parsers are split into two modules
# (`perf_stat_text` and `perf_stat_csv`) — see README.md for details.
#
# Important note on perf availability: `perf` lives in the
# `linux-tools-<kernel>` packages on Debian/Ubuntu and often requires
# `kernel.perf_event_paranoid <= 2` (or lower, depending on which
# events are counted) to run unprivileged. On GitHub-hosted runners,
# `perf_event_paranoid` is typically set to `4` and sysctl writes may
# be restricted, which means this workflow may legitimately fail to
# produce useful counter data. The workflow YAML documents the
# fallback: if perf refuses to run, we capture `perf --version` and
# the error message so the fixture still exists as a record of the
# environment.
#
# perf stat flags used below:
#
#   -o FILE       write output to FILE instead of stderr
#   -x,           machine-readable output with `,` as field separator
#                 (CSV-ish; see README for the column list and gotchas)
#
# The default counter set (task-clock, context-switches, page-faults,
# cycles, instructions, branches, branch-misses) is used — we do NOT
# pass `-e` to pin specific events, because the available events vary
# by CPU / kernel and we want the fixture to reflect what users would
# actually see on the runner they're on.
set -euo pipefail

cd "$(dirname "$0")"
chmod +x benchmark1.sh benchmark2.sh benchmark3.sh benchmark4.sh

# Clean slate each run.
: > output-text.txt
: > output-csv.txt

# Sanity-check that perf is present and usable. If it isn't, write a
# diagnostic fixture so the artifact upload still succeeds — that way
# a parser-author reviewing the captured output can see *why* perf
# didn't produce real counter data on this runner.
if ! command -v perf >/dev/null 2>&1; then
    {
        echo "=== perf not available ==="
        echo "perf binary not found on PATH. See README for install notes."
    } >> output-text.txt
    {
        echo "=== perf not available ==="
        echo "perf binary not found on PATH. See README for install notes."
    } >> output-csv.txt
    echo "perf not available; wrote diagnostic fixtures" >&2
    exit 0
fi

# Record perf version up top in both output files so drifts in format
# across kernel / perf versions are attributable.
{
    echo "=== perf --version ==="
    perf --version 2>&1 || true
    echo
} >> output-text.txt
{
    echo "=== perf --version ==="
    perf --version 2>&1 || true
    echo
} >> output-csv.txt

# --- 1. default text format -------------------------------------------------
#
# `perf stat -o FILE` writes the counter summary to FILE; the timed
# command's own stdout/stderr still goes through to our shell. We
# emit separator lines around each invocation so the parser can key
# each block to a test_name.
for bm in benchmark1 benchmark2 benchmark3 benchmark4; do
    {
        echo "=== ${bm} (perf stat, text) ==="
    } >> output-text.txt
    # Run the benchmark under perf stat. If perf fails (e.g. because
    # kernel.perf_event_paranoid blocks us), capture the error
    # message into the output file rather than aborting the whole
    # script — partial fixtures are more useful than none.
    if ! perf stat -o output-text.txt --append "./${bm}.sh" \
           >>output-text.txt 2>>output-text.txt; then
        echo "(perf stat exited non-zero for ${bm} — see above)" >> output-text.txt
    fi
    {
        echo "=== end ${bm} ==="
        echo
    } >> output-text.txt
done

# --- 2. CSV format (-x,) ----------------------------------------------------
#
# With `-x,` perf emits one line per counter with `,` as the field
# separator. The column layout (summarized in README) is
# <value>,<unit>,<event>,<running_time>,<pcnt>,... and is stable
# across modern perf versions. The unit column is often blank (only
# populated for events like task-clock that have a natural unit like
# msec, or power/energy events measured in Joules).
for bm in benchmark1 benchmark2 benchmark3 benchmark4; do
    {
        echo "=== ${bm} (perf stat, csv) ==="
    } >> output-csv.txt
    if ! perf stat -x, -o output-csv.txt --append "./${bm}.sh" \
           >>output-csv.txt 2>>output-csv.txt; then
        echo "(perf stat exited non-zero for ${bm} — see above)" >> output-csv.txt
    fi
    {
        echo "=== end ${bm} ==="
        echo
    } >> output-csv.txt
done

echo "Wrote output-text.txt and output-csv.txt"
