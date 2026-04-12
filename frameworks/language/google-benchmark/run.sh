#!/bin/bash
# Build the Google Benchmark sample and capture all three output formats.
#
# Configure + build via CMake in Release mode (benchmark libraries are
# sensitive to optimization level — Debug builds produce meaninglessly
# slow results and would make test 2 useless).
#
# Google Benchmark has two independent output controls:
#   --benchmark_out / --benchmark_out_format  → file output
#   --benchmark_format                        → stdout output
# We exploit this to capture two formats per run, then do one extra
# run for the third format.
#
#   Run 1: JSON to file  +  console text to stdout (→ tee output.txt)
#   Run 2: CSV to file   (stdout discarded)
#
# Keeping this in a shell script (rather than inline in the workflow
# YAML) makes it easy to iterate locally via `act` or a direct
# `./run.sh` from this directory.
set -euo pipefail

cd "$(dirname "$0")"

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release

# Run 1: JSON file output + console text on stdout captured via tee.
./build/sample_benchmark \
    --benchmark_out=output.json \
    --benchmark_out_format=json \
    --benchmark_format=console 2>&1 | tee output.txt

# Run 2: CSV file output.
./build/sample_benchmark \
    --benchmark_out=output.csv \
    --benchmark_out_format=csv
