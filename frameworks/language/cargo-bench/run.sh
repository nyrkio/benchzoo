#!/bin/bash
# Run the canonical sample benchmark under `cargo bench` (libtest) and
# capture the combined stdout+stderr into ./output.txt.
#
# libtest's output format is one line per `#[bench]` fn:
#
#   test benchmark1 ... bench:  2150123486 ns/iter (+/- 10172)
#
# plus some surrounding lines like the "running N tests" header and the
# final "test result: ok." summary. The benchzoo parser
# (src/benchzoo/parsers/cargo_bench_libtest.py — not yet written)
# ignores everything except the `test <name> ... bench:` lines, so the
# surrounding chatter is harmless.
#
# NIGHTLY REQUIRED. `#[bench]` is unstable. The toolchain is pinned by
# `rust-toolchain.toml` in this same directory, so plain `cargo bench`
# picks up the right nightly automatically. We still spell out
# `cargo +nightly` for belt-and-suspenders clarity in case someone runs
# this script from outside the directory.
set -euo pipefail

cd "$(dirname "$0")"

rm -f output.txt

# Capture both stdout and stderr. libtest writes the bench result lines
# to stdout; cargo itself prints compilation progress to stderr. Merging
# them into one file keeps the artifact shape simple (one file, one
# parser input).
cargo +nightly bench > output.txt 2>&1

echo "--- output.txt ---"
cat output.txt
