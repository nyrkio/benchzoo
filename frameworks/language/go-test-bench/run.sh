#!/bin/bash
# Run the canonical sample benchmark under `go test -bench` and write
# the captured text output to ./output.txt. This is the command the
# workflow (and a local `act` run) execute; keeping it in a script
# rather than inline in the YAML makes it easy to iterate locally.
#
# Flag rationale:
#
#   -bench=.        run every Benchmark* function in the package
#   -run=^$         skip non-benchmark tests (there are none, but be
#                   explicit — otherwise `go test` also runs Test* funcs)
#   -benchmem       report allocations per op, which the parser may use
#   -benchtime=1x   pin b.N = 1 for every benchmark
#
# The -benchtime=1x choice is the load-bearing one. Go's default is
# -benchtime=1s, which re-runs the benchmarked body until the elapsed
# wall time exceeds one second. For test 1 (2.15 s sleep), one iteration
# already blows past the target, so b.N converges to 1 anyway — but
# relying on that is brittle. And for test 2 (tight loop), the default
# would run the loop hundreds of millions of times, producing ns/op
# numbers that no longer correspond to "one pass through the 1000-element
# loop" and therefore can't be compared to the ground-truth values in
# docs/sample-benchmark.md.
#
# Pinning -benchtime=1x makes every reported ns/op equal to the wall
# time of one invocation of the benchmark body, which is exactly the
# semantic the canonical suite is written against. The trade-off is
# that test 2 becomes a single-sample measurement with high variance;
# we accept that because variance isn't what test 2 is verifying (see
# sample-benchmark.md, "Test 2 will be the noisiest").
#
# Output capture: we redirect both stdout and stderr into output.txt.
# `go test -bench`'s default text format is very regular — lines of the
# form:
#
#   BenchmarkBenchmark1-8   1   2150123456 ns/op    0 B/op   0 allocs/op
#
# — and is what the parser will consume. An alternative capture mode is
# `go test -json`, which emits a line-delimited stream of test events;
# that is a separate parser target (parser-targets.md section 6,
# "go test -json") with its own fixture and its own parser. We stick to
# the text format here.
set -euo pipefail

cd "$(dirname "$0")"

go test -bench=. -benchmem -run=^$ -benchtime=1x ./... > output.txt 2>&1

# Second pass: capture the same benchmarks in Go's streaming JSON format
# (`go test -json`). This is a separate parser target (parser-targets.md
# section 6) producing line-delimited JSON — one object per test event.
go test -bench=. -benchmem -run='^$' -benchtime=1x -json ./... > output.json 2>&1
