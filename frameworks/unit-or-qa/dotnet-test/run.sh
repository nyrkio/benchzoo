#!/bin/bash
# Run the xUnit canonical sample benchmark under `dotnet test` with the
# TRX (Visual Studio Test Results) logger. TRX is Microsoft's native
# test-report XML format — distinct from the JUnit XML that
# `--logger junit` would produce (that variant gets its own benchzoo
# framework directory and parser).
#
# `dotnet test` writes per-test results — including a `duration`
# attribute in `hh:mm:ss.fffffff` format — to the TRX file. The run.sh
# contract across the benchzoo corpus is "this script leaves
# ./output.<ext> files behind" — we point TRX's LogFileName directly at
# output.trx and its results directory at `.` so the file lands where
# the workflow's upload-artifact step expects it.
set -euo pipefail

cd "$(dirname "$0")"

rm -f ./output.trx

dotnet test \
    --logger "trx;LogFileName=output.trx" \
    --results-directory .
