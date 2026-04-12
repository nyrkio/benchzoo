# junit-go

Regular Go unit tests (`go test`) wrapped by
[`gotestsum`](https://github.com/gotestyourself/gotestsum) to produce
JUnit XML. Per-test wall-clock duration from the JUnit `<testcase>`
`time` attribute is the signal — the test runner is used as a timing
source, not as a benchmarking framework.

This is **distinct** from the
[`go-test-bench`](../../language/go-test-bench/) framework, which
exercises Go's native `testing.B` / `go test -bench` machinery, and
also distinct from `go test -json` for unit tests (a separate parser
target — see [`parser-targets.md`](../../../docs/parser-targets.md)
section 6). Same binary (`go test`), three different output families,
three different parsers.

## Links

- **Sample benchmark** — [`sample_test.go`](sample_test.go),
  orchestrated by [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/junit-go.yml`](../../../.github/workflows/junit-go.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/junit-go.yml>
- **Parser** — [`src/benchzoo/parsers/junit_go.py`](../../../src/benchzoo/parsers/junit_go.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_junit_go.py`](../../../tests/parsers/test_junit_go.py) *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
`go test` / gotestsum idiom, as four `TestBenchmarkN` functions in
[`sample_test.go`](sample_test.go):

- **Test 1** (sleep 2.15 s) — `TestBenchmark1` calls
  `time.Sleep(2150 * time.Millisecond)`.
- **Test 2** (tight CPU loop) — `TestBenchmark2` runs
  `for j := 0; j < 1000; j++ { sum += j }` and passes `sum` to
  `runtime.KeepAlive` at the end. Without that, Go's optimizer deletes
  the loop entirely (no observable side effect), and the test measures
  nothing. `runtime.KeepAlive` is Go's equivalent of Rust's
  `std::hint::black_box` or JMH's `Blackhole.consume`.
- **Test 3** (write 1.4 MB to /dev/null) — `TestBenchmark3` opens
  `/dev/null` with `os.OpenFile` and writes 1,400,000 bytes of
  pseudo-random data using `io.Copy` over a trivial in-memory
  `io.Reader`. `math/rand` (not `crypto/rand`) is used because
  randomness quality isn't the point and `math/rand` is substantially
  faster.
- **Test 4** (monthly change point) — `TestBenchmark4` reads
  `time.Now().UTC().Month()` and sleeps for
  `2.15 + ((m mod 3) - 1)` seconds.

These are `Test*` functions, **not** `Benchmark*` functions —
`Benchmark*` is how `go test -bench` discovers benchmarks, and that
framework is handled separately under
[`frameworks/language/go-test-bench/`](../../language/go-test-bench/).
Here we're deliberately using `go test`'s per-test timing as the
performance signal, so the functions are ordinary unit tests.

The orchestration lives in [`run.sh`](run.sh), which `go install`s
`gotest.tools/gotestsum@v1.12.0` (version pinned per
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#versioning-the-framework))
and then invokes:

```
gotestsum --format=standard-verbose --junitfile=output.xml ./...
```

`--format=standard-verbose` keeps a human-readable live log on stdout;
`--junitfile=output.xml` writes the JUnit XML the parser will consume.

## Running locally

```bash
act push -W .github/workflows/junit-go.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/junit-go-output/output.xml`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with Go installed locally, `./run.sh` from this
directory produces the same `output.xml` without the GitHub Actions
artifact plumbing.

## Parser notes

gotestsum emits standard JUnit XML: `<testsuites>` containing
`<testsuite>` containing `<testcase>` elements. The `junit_go` parser
reads each `<testcase>`'s `time` attribute (seconds, as a decimal
string) and emits it as a single `duration` metric per test — the
"unit-test runner as a timing source" shape described in
[`docs/design.md`](../../../docs/design.md). This is the same
structural strategy used by
[`junit_pytest`](../../../src/benchzoo/parsers/junit_pytest.py)
when no benchmark `<properties>` are present; cross-reference that
parser's fallback branch for the expected metric shape. Unlike
pytest-benchmark, gotestsum does not write benchmark-stat
`<properties>` — every `junit_go` test is the "fallback" shape.

### Test name normalization

Go test functions are named `TestBenchmark1`, `TestBenchmark2`, etc.
— Go's convention requires a `Test` prefix on every test function.
The parser should strip that prefix and lowercase the remainder to
get the canonical test names used across benchzoo:

```
TestBenchmark1 → benchmark1
TestBenchmark2 → benchmark2
TestBenchmark3 → benchmark3
TestBenchmark4 → benchmark4
```

This mirrors what
[`junit_pytest`](../../../src/benchzoo/parsers/junit_pytest.py) does
with its `test_` prefix (`test_benchmark1 → benchmark1`). The exact
stripping rule differs — `Test` vs. `test_`, Go's PascalCase vs.
pytest's snake_case — but the principle is the same: the canonical
`test_name` does not carry the language-ecosystem prefix the runner
required us to write into the source.

### Pass/fail

`<failure>` or `<error>` children on a `<testcase>` flip
`passed: false` on that result dict, following the same convention as
`junit_pytest`. gotestsum also records skipped tests via `<skipped>`;
the canonical suite has none, but the parser should tolerate them
(treat as passed with whatever timing gotestsum reported, or document
the handling).

### Direction

`duration` is a cost; `direction: "lower_is_better"`. Same as
`junit_pytest`'s fallback branch.
