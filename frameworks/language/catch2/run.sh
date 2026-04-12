#!/bin/bash
# Build the Catch2 sample and capture all common output formats.
#
# Configure + build via CMake in Release mode (benchmark libraries are
# sensitive to optimization level — Debug builds produce meaninglessly
# slow results and would make test 2 useless).
#
# Catch2 v3 selects its reporter via --reporter <name>; the default is
# the human-readable "console" table. For machine-readable fixtures we
# also capture "xml" (Catch2's native structured format, rich) and
# "junit" (standard JUnit XML, which a future `junit_catch2` parser
# will consume — see docs/parser-targets.md section 6). JSON is
# available on newer Catch2 versions but is not yet as stable as XML,
# so we capture it optionally and tolerate failure.
#
# Each reporter run is a separate invocation of the binary. Catch2
# supports multiple --reporter flags in a single run with
# "reporter::file=path", but for clarity and to keep the script
# readable we run it once per format.
set -euo pipefail

cd "$(dirname "$0")"

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release

BIN=./build/sample_benchmark

# Cap benchmark samples to keep the CI run time bounded. Catch2's
# default is 100 samples per benchmark; with our sleep-heavy tests 1
# and 4 (~2.15 s each) that would be ~215 s per test per reporter
# invocation, and we run the binary once per reporter — north of 1000 s
# total. 3 samples is enough to exercise the parser's handling of
# mean/low/high; statistical tightness is not what this corpus tests.
SAMPLES=--benchmark-samples=3

# Console text (default reporter) — piped through tee so we retain
# both stdout visibility in the CI log and a captured output.txt.
"$BIN" $SAMPLES --reporter console 2>&1 | tee output.txt

# Catch2's native XML reporter — richest structured format.
"$BIN" $SAMPLES --reporter xml --out output.xml

# JUnit XML — consumed by the planned junit_catch2 parser.
"$BIN" $SAMPLES --reporter junit --out output.junit.xml

# JSON reporter — available on Catch2 v3.4+ . Best-effort: older
# versions fail here, and that's fine; the other three formats cover
# us. Remove the `|| true` once the pinned Catch2 version is known to
# ship the JSON reporter.
"$BIN" $SAMPLES --reporter json --out output.json || true
