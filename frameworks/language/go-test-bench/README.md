# go test -bench

[`go test -bench`](https://pkg.go.dev/testing#hdr-Benchmarks) is Go's
standard library benchmark support, built into the `testing` package.
Benchmark functions take a `*testing.B` and run their body `b.N` times,
with `b.N` auto-calibrated by the framework to hit a target wall time.
It's the universal Go benchmarking tool — every Go project that measures
performance uses it, usually in combination with `benchstat` for
statistical aggregation across repeated runs.

## Links

- **Sample benchmark** — [`benchmarks_test.go`](benchmarks_test.go),
  orchestrated by [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/go-test-bench.yml`](../../../.github/workflows/go-test-bench.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/go-test-bench.yml>
- **Parser** — [`src/benchzoo/parsers/go_test_bench.py`](../../../src/benchzoo/parsers/go_test_bench.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_go_test_bench.py`](../../../tests/parsers/test_go_test_bench.py) *(not yet written)*

The predecessor TypeScript project at
[`nyrkio/change-detection`](https://github.com/nyrkio/change-detection)
shipped a `go test -bench` parser — reference-only, not imported by
benchzoo.

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
`go test -bench` idiom, as four `BenchmarkBenchmarkN` functions in
[`benchmarks_test.go`](benchmarks_test.go):

- **Test 1** (sleep 2.15 s) — `BenchmarkBenchmark1` calls
  `time.Sleep(2150 * time.Millisecond)` inside the `b.N` loop. With
  `-benchtime=1x` (see below) `b.N` is pinned to 1, so the reported
  `ns/op` is the wall time of a single 2.15 s sleep.
- **Test 2** (tight CPU loop) — `BenchmarkBenchmark2` runs
  `for j := 0; j < 1000; j++ { sum += j }` and passes `sum` to
  `runtime.KeepAlive` at the end. Without that, Go's optimizer deletes
  the loop entirely (it has no observable side effect), which would
  make the benchmark measure nothing and report ns/op of roughly zero.
  `runtime.KeepAlive` is Go's equivalent of Rust's `std::hint::black_box`
  or JMH's `Blackhole.consume`. Go 1.24 introduces a nicer
  `b.Loop()`-based idiom that would let us drop the manual accumulator,
  but we pin Go 1.22 so the KeepAlive shape is what ships here.
- **Test 3** (write 1.4 MB to /dev/null) — `BenchmarkBenchmark3` opens
  `/dev/null` with `os.OpenFile` and writes 1,400,000 bytes of
  pseudo-random data per iteration, seeded deterministically.
  `math/rand` (not `crypto/rand`) is used because randomness quality
  isn't the point, and `math/rand` is substantially faster, keeping
  test 3 in the "small and cheap" regime the canonical suite calls for.
- **Test 4** (monthly change point) — `BenchmarkBenchmark4` reads
  `time.Now().UTC().Month()` and sleeps for `2.15 + ((m mod 3) - 1)`
  seconds.

The orchestration lives in [`run.sh`](run.sh), which invokes
`go test -bench=. -benchmem -run=^$ -benchtime=1x ./...` and redirects
both stdout and stderr into `output.txt`. Keeping the invocation in a
shell script (rather than inline in the workflow YAML) makes it easy to
iterate locally via `act` or a direct `./run.sh`.

## Running locally

```bash
act push -W .github/workflows/go-test-bench.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/go-test-bench-output/output.txt`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with Go installed locally, you can bypass `act` entirely
and just run `./run.sh` from this directory. That produces the same
`output.txt` but without the GitHub Actions artifact plumbing.

## Parser notes

`go test -bench`'s default text format is very regular and easy to
parse. Each benchmark produces one line of the form:

```
BenchmarkName-cpus   N   X ns/op   [Y B/op   Z allocs/op]
```

where:

- `BenchmarkName` is the Go function name (e.g. `BenchmarkBenchmark1`).
  The parser should strip the leading `Benchmark` and map the remainder
  to `attributes["test_name"]` — for the canonical suite that yields
  `benchmark1` .. `benchmark4` after lowercasing.
- `-cpus` is a suffix giving `GOMAXPROCS` (e.g. `-8` on an 8-core
  runner). It's part of the line, not the name; strip it before mapping
  to `test_name`.
- `N` is `b.N`, the iteration count the framework converged on. With
  `-benchtime=1x` it's always `1` for this suite.
- `X ns/op` is the mean wall-clock time per iteration in nanoseconds —
  this is the headline metric. Ground-truth: test 1 should fall near
  `2.15e9`, test 4 near `{1.15, 2.15, 3.15}e9`.
- `B/op` and `allocs/op` (emitted because `run.sh` passes `-benchmem`)
  are bytes-allocated and allocation count per iteration. Both are
  worth capturing as separate metrics with units `"bytes"` and `"count"`
  respectively.

Other lines in `output.txt` to be aware of:

- Leading `goos:`, `goarch:`, `pkg:`, `cpu:` preamble lines. These are
  environment metadata; a parser may stash them in `extra_info` or drop
  them. They are **not** per-test data.
- `PASS` / `FAIL` / `ok` footer lines. `FAIL` on an individual
  benchmark should flip `passed: false` for that test.
- Lines from `b.Logf` (e.g. test 4 logs its month and sleep duration).
  These land in `output.txt` interleaved with the benchmark result
  lines. A parser should either match the benchmark line by a strict
  regex (not "starts with `Benchmark`") or tolerate log lines between
  benchmark lines.

### The `-benchtime=1x` rationale

The load-bearing choice in `run.sh` is `-benchtime=1x`, which pins
`b.N = 1` for every benchmark. Go's default is `-benchtime=1s`, which
re-runs the body until elapsed wall time exceeds one second. For test 1
(2.15 s sleep) that's fine — one iteration already overshoots. For
test 2 (tight loop), the default would run the loop hundreds of
millions of times to hit the 1 s target, which is *exactly how Go
benchmarking is supposed to work* but produces a ns/op value that
corresponds to "one pass through the 1000-element loop", not to one
invocation of `BenchmarkBenchmark2`. That in turn doesn't match the
ground-truth values in [`sample-benchmark.md`](../../../docs/sample-benchmark.md),
which are specified per-test, not per-inner-iteration.

Pinning `b.N = 1` makes every reported `ns/op` the wall time of one
invocation of the benchmark body, which is the semantic the canonical
suite is written against. The trade-off is that test 2 becomes a
single-sample measurement with high variance — but variance isn't what
test 2 is verifying (see sample-benchmark.md's "Test 2 will be the
noisiest" note).

### JSON capture: `go test -json`

`run.sh` now performs a second `go test` invocation with the `-json`
flag, writing `output.json` alongside the text `output.txt`. The JSON
format is line-delimited — one JSON object per line — with each object
representing a test event. Objects with `"Test"` set to a benchmark
name carry these fields:

- `Action` — event type (`"output"`, `"run"`, `"bench"`, `"pass"`,
  `"fail"`, etc.)
- `Package` — the Go package under test
- `Test` — benchmark function name (e.g. `"BenchmarkBenchmark1"`)
- `Output` — a string containing one line of text output (the familiar
  `BenchmarkName-N  iterations  ns/op` lines appear here, embedded
  inside the JSON stream)
- `Elapsed` — seconds elapsed for the event (present on pass/fail
  events)

The text parser (`go_bench_text.py`) and JSON parser
(`go_bench_json.py`) are separate modules. The text format is simpler
and more commonly used; the JSON format is richer, including test
pass/fail events, package-level timing, and structured metadata that
the text format omits. See
[`parser-targets.md`](../../../docs/parser-targets.md) section 6
("go test -json") for the full parser-target specification.

### Direction

Every metric `go test -bench` reports here is a cost: nanoseconds per
op, bytes allocated per op, allocations per op. All get
`direction: "lower_is_better"`.
