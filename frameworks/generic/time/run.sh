#!/bin/bash
# Run all four canonical sample-benchmark tests under two different
# "Unix time" implementations and capture their outputs side by side:
#
#   1. bash's builtin `time` keyword  -> output-builtin.txt
#   2. GNU /usr/bin/time -v            -> output-gnu.txt
#
# Both formats are valuable fixtures. They are *different formats* with
# different field sets, so downstream parsers are split into two
# modules (`time_builtin` and `time_gnu`) — see README.md for details.
#
# Important bash quirk: `time` is a **reserved word**, not a command.
# It times a *pipeline*, not an argv[]. It cannot be stored in a
# variable, aliased, or called via `$(which time)`. It must appear
# inline. Its output (the `real`/`user`/`sys` lines) goes to the
# shell's stderr — so to capture it we wrap the timed command plus
# our separator echos in a `{ ... } >> file 2>&1` compound, which
# merges stdout and stderr into the output file in order.
#
# GNU /usr/bin/time is a normal binary (apt package `time` on Debian /
# Ubuntu). `-v` enables the verbose multi-line format (maxrss, page
# faults, cpu%, etc.). `-o FILE` writes to FILE instead of stderr;
# `-a` appends rather than truncating, which lets us accumulate all
# four runs into one file.
#
# We print plain-text `=== benchmarkN (...) ===` separators between
# benchmarks so a human (and the future parser) can tell where one
# run ends and the next begins, and can key each block to its
# `test_name` via the separator.
set -euo pipefail

cd "$(dirname "$0")"
chmod +x benchmark1.sh benchmark2.sh benchmark3.sh benchmark4.sh

# Start from a clean slate every run so the captured fixture reflects
# only this invocation, not a pileup across iterations.
: > output-builtin.txt
: > output-gnu.txt

# --- 1. bash builtin `time` -------------------------------------------------
#
# The builtin prints three lines (`real`, `user`, `sys`) to stderr after
# the pipeline finishes. We redirect the whole `{ ... }` group's stdout
# *and* stderr to the output file with `>> file 2>&1` so everything
# lands in order: our separator echos, the benchmark's own "Starting
# .../End of ..." echos, and the `time` summary from stderr. The
# parser only needs the `real/user/sys` block but it's useful to keep
# the surrounding context for debugging.
for bm in benchmark1 benchmark2 benchmark3 benchmark4; do
    {
        echo "=== ${bm} (bash builtin time) ==="
        # `time` is a reserved word; it has to be inline like this.
        # It cannot be stored in a variable or called as `$(which time)`.
        time "./${bm}.sh"
        echo "=== end ${bm} ==="
        echo
    } >> output-builtin.txt 2>&1
done

# --- 2. /usr/bin/time -v ----------------------------------------------------
#
# GNU time's verbose format is ~23 lines of "Label: value" pairs. We
# prepend a separator of our own via plain `>>` before each invocation
# so the parser can key each block to a test name. `-a` appends.
for bm in benchmark1 benchmark2 benchmark3 benchmark4; do
    {
        echo "=== ${bm} (/usr/bin/time -v) ==="
    } >> output-gnu.txt
    /usr/bin/time -v -o output-gnu.txt -a "./${bm}.sh"
    {
        echo "=== end ${bm} ==="
        echo
    } >> output-gnu.txt
done

echo "Wrote output-builtin.txt and output-gnu.txt"
