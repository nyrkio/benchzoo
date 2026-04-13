# ctest

[CTest](https://cmake.org/cmake/help/latest/manual/ctest.1.html) is
CMake's built-in test runner. `add_test(...)` registers an arbitrary
command as a test; `ctest` runs each registered command, records
pass/fail (by exit code) and wall-clock duration, and — since CMake
3.21 — can emit a standard junit XML report via `--output-junit
<file>`.

CTest is a test *runner*, not a benchmarking framework. The "metric"
it captures is whichever wall-clock duration the test command
happened to take. For benchzoo that is exactly enough: the canonical
sample benchmark's tests 1, 3, and 4 are all wall-time-dominated, so
CTest's `time` attribute is the number we care about.

## Links

- **Sample benchmark** — the four shell scripts in this directory
  ([`benchmark1.sh`](benchmark1.sh) .. [`benchmark4.sh`](benchmark4.sh)),
  wired up via [`CMakeLists.txt`](CMakeLists.txt) and orchestrated by
  [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/ctest.yml`](../../../.github/workflows/ctest.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/ctest.yml>
- **Parser** — [`src/benchzoo/parsers/junit_standard.py`](../../../src/benchzoo/parsers/junit_standard.py) — shared with `junit-vanilla`, `junit-jest`, and `catch2`'s junit reporter
- **Parser tests** — `tests/parsers/test_batch5.py::test_junit_standard_ctest`

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) as
four `add_test` registrations in [`CMakeLists.txt`](CMakeLists.txt),
each invoking one of the four shell scripts:

- **Test 1** (sleep 2.15 s) — [`benchmark1.sh`](benchmark1.sh) runs
  `sleep 2.15`. CTest records the full wall time including the
  `bash` startup overhead (small — a few ms).
- **Test 2** (tight CPU loop) — [`benchmark2.sh`](benchmark2.sh)
  runs `for ((i=0; i<1000; i++)); do :; done`. Bash is interpreted,
  so no `black_box`-style guard is needed to keep the loop from
  being optimized away. The measured time here is dominated by bash
  startup, not by the loop itself — test 2's role in the CTest
  surface is to exercise sub-millisecond-ish parser handling, not to
  produce a physically meaningful loop time.
- **Test 3** (write 1.4 MB to /dev/null) — [`benchmark3.sh`](benchmark3.sh)
  runs `head -c 1400000 /dev/urandom > /dev/null`. Exactly
  1,400,000 bytes (decimal MB, not binary MiB — see the size
  convention note in
  [`sample-benchmark.md`](../../../docs/sample-benchmark.md#test-3--small-write-to-devnull-14-mb)).
- **Test 4** (monthly change point) — [`benchmark4.sh`](benchmark4.sh)
  reads the current UTC month and sleeps for
  `2.15 + ((m mod 3) - 1)` seconds.

Registration lives in [`CMakeLists.txt`](CMakeLists.txt) and uses a
`foreach(n RANGE 1 4)` loop so the four `add_test` calls stay in
sync with the four shell scripts by construction. The project is
declared with `project(... NONE)` — we don't compile anything, we
only register and run shell commands — so neither a C nor a C++
compiler is required to run this framework. Only CMake (>= 3.21 for
`--output-junit`) and `bash`.

### Build & run

[`run.sh`](run.sh) does the usual CMake dance (`cmake -S . -B build`
then `cmake --build build`) and finishes with
`ctest --output-junit ../output.xml` from inside the build
directory. The resulting `output.xml` is a standard junit report,
uploaded as the workflow artifact.

## Running locally

```bash
act push -W .github/workflows/ctest.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/ctest-output/output.xml`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with CMake 3.21+ and bash installed locally, you can
bypass `act` entirely and run `bash run.sh` from this directory.

## Parser notes

CTest's `--output-junit` writes a standard junit report: a single
`<testsuite>` containing one `<testcase>` per registered test, with
`name` (the `add_test(NAME ...)` value — here `benchmark1` ..
`benchmark4`), `classname` (CTest uses the project name, e.g.
`benchzoo_ctest_sample`), and a `time` attribute giving CTest's
measured wall-clock duration in seconds. Test failures surface as a
`<failure>` child on the testcase.

The parser module is **`junit_standard`** — the same shared parser
used by `junit-vanilla`, `junit-jest`, and `catch2`'s junit reporter.
CTest's `--output-junit` emits structurally plain junit XML: `time` is
the process wall time in seconds (one `duration` metric per testcase,
`lower_is_better`), `name` holds the `add_test(NAME ...)` value
verbatim (used directly as `test_name` — our `add_test(NAME benchmarkN)`
calls already use the canonical names), and `<failure>` children flip
`passed` to `false`. `classname` carries the CMake project name; the
shared parser ignores it.

### Ground-truth assertions

The canonical ground-truth values from
[`docs/sample-benchmark.md`](../../../docs/sample-benchmark.md#ground-truth-values-and-why-they-matter)
apply: test 1's `time` should be `2.0 < t < 2.3` seconds. Test 2's
`time` will be dominated by bash startup (tens of milliseconds),
not loop execution. Test 3's `time` will be a few tens of ms at
most.
