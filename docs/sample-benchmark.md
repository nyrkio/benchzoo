# The canonical sample benchmark

A small, fixed benchmark suite that we will implement across **every
framework** in [`parser-targets.md`](parser-targets.md). Each framework runs
the same three tests, producing native output that we then use as a
real-world fixture for our parsers.

## Why three tests with such different characteristics

- **Different magnitudes** (seconds vs. microseconds vs. small I/O)
  stress-test parsers across the range of timings they will encounter in the
  wild. A parser that rounds sub-millisecond times to zero will fail on test
  2; a parser that overflows on multi-second values will fail on test 1.
- **A non-round duration (2.15 s)** makes it obvious when a parser truncates
  precision or rounds to whole seconds.
- **A non-round byte count (1.4 MB)** does the same for I/O-shaped metrics.
- **Three tests** means we exercise the per-test breakdown that most
  frameworks emit — not just a single overall measurement. Parsers that only
  return aggregate numbers will be visibly wrong.

The number "three" and the specific tests are a starting point, not set in
stone. If a particular framework idiom calls for a different shape, we can
adjust.

## Test 1 — Sleep-dominated (~2.15 s)

Wall time roughly 2.15 seconds, dominated by `sleep`. Verifies the parser
captures the full elapsed time, not just CPU time.

```
print "Starting benchmark1"
sleep 2.15 seconds        # 2 seconds and 150 milliseconds
print "End of benchmark1"
```

## Test 2 — Tight CPU loop (sub-millisecond)

Very short, CPU-bound. Counts from 0 to 1000 in a `for` loop, then exits.
Verifies the parser handles sub-millisecond / sub-microsecond durations
without rounding to zero.

```
print "Starting benchmark2"
for i in 0..1000:
    (no body)
print "End of benchmark2"
```

**Note on optimization:** an empty loop counting to 1000 will be deleted
entirely by an optimizing compiler in Rust, C++, Go, etc. When implementing
in compiled languages, we may need to either disable optimization, use a
side-effecting body (e.g. accumulate into a `volatile`/`black_box` sink), or
use the framework's idiomatic "this is a benchmark, don't optimize this
away" mechanism (`std::hint::black_box` in Rust, `Blackhole.consume` in JMH,
etc.).

## Test 3 — Small write to /dev/null (1.4 MB)

Writes exactly 1.4 MB of pseudo-random data to `/dev/null` and exits.
Verifies the parser handles I/O-shaped tests with non-round byte counts.

```
print "Starting benchmark3"
write 1_400_000 bytes of random data to /dev/null
print "End of benchmark3"
```

**Note on size convention:** "1.4 MB" is interpreted as decimal —
1,400,000 bytes — not binary 1.4 MiB (1,468,006 bytes). The discrepancy
matters less than the consistency: we use decimal across all
implementations.

**Note on /dev/null:** writing to `/dev/null` is not a real I/O test — the
kernel discards the bytes and never touches a disk. That is intentional.
We want a small, cheap, deterministic operation to compare across
frameworks, not a meaningful storage benchmark.

## Test 4 — Change-detection showcase (monthly change point)

Test 4 is the same *shape* as test 1 — a sleep followed by an echo —
**except the sleep duration depends on the current month**, producing a
deterministic step-function time series with one change point at every
month boundary.

The purpose of test 4 is different from tests 1–3: it exists not for
parser-layer testing but to **showcase change-point detection** (see
[Apache Otava in `design.md`](design.md#what-it-is-not)). A single run
tells you almost nothing. Many runs over time produce a known signal
that an eventual ingest → Otava pipeline can be asserted against.

### Formula

Let `m` be the current month (1..12, UTC). Test 4's sleep duration in
seconds is:

```
sleep_time = 2.15 + ((m mod 3) - 1)
```

Expanded per month:

| month     | m  | (m mod 3) − 1 | sleep_time |
| --------- | -- | ------------- | ---------- |
| January   |  1 |  0            | **2.15 s** |
| February  |  2 |  1            | **3.15 s** |
| March     |  3 | −1            | **1.15 s** |
| April     |  4 |  0            | **2.15 s** |
| May       |  5 |  1            | **3.15 s** |
| June      |  6 | −1            | **1.15 s** |
| July      |  7 |  0            | **2.15 s** |
| August    |  8 |  1            | **3.15 s** |
| September |  9 | −1            | **1.15 s** |
| October   | 10 |  0            | **2.15 s** |
| November  | 11 |  1            | **3.15 s** |
| December  | 12 | −1            | **1.15 s** |

The sequence cycles through `{1.15 s, 2.15 s, 3.15 s}` with period
3 months. Every month boundary is a step change, so a full calendar
year produces **11 change points**. `m` is always read as **UTC month**
so runners in different timezones produce the same value on the same
calendar day.

### Purpose (why test 4 is different)

Tests 1–3 exist to verify parsers capture timing correctly, via
ground-truth assertions against fixed expected values. Test 4 exists to
exercise the full pipeline against a signal with a known change-point
structure:

- **One run** of test 4 produces one datapoint — useful for verifying
  the parser reads a numeric value, not much more.
- **Many runs over time** (one per day, across months) produce a
  step-function time series. Once the ingest + Otava layers exist, the
  pipeline can be asserted against the known structure: "after 12
  months of runs, Otava should have reported 11 change points at
  specific month boundaries."
- This means test 4 is **only meaningful when the workflow runs
  regularly over time**, not just on push/PR. See the `schedule:`
  trigger note in
  [`workflow-conventions.md`](workflow-conventions.md#optional-scheduled-runs-for-test-4--change-detection-showcase).

### Bash reference implementation

`benchmark4.sh`:

```bash
#!/bin/bash
echo "Starting benchmark4"
m=$(date -u +%-m)                                # 1..12, UTC, no leading zero
sleep_s=$(awk "BEGIN { print 2.15 + ($m % 3) - 1 }")
echo "benchmark4: month=$m, sleep=${sleep_s}s"
sleep "${sleep_s}"
echo "End of benchmark4"
```

Notes:

- `-u` forces UTC.
- `%-m` strips the leading zero so `m` is an integer.
- bash's `$((…))` only handles integers, so `awk` does the float
  arithmetic. `bc -l` would work too.
- GNU `sleep` accepts a bare float like `2.15`, no trailing `s` needed.

### Ground-truth assertion for test 4

Unlike tests 1–3, test 4's expected wall time depends on when the
fixture was captured. Parser tests can either:

1. **Loose check** — assert the value is one of `{1.15, 2.15, 3.15}`
   (with tolerance). Portable, no dependency on capture metadata.
2. **Exact check, if the capture month is known** — assert the value
   matches the formula for that specific month. Stronger, but requires
   the fixture to carry or be accompanied by its capture month (sidecar
   file, naming convention, or a month field embedded in the output).

Both are acceptable. Start with the loose check. Upgrade to the exact
check only if and when fixtures grow sidecar metadata — don't jump
through hoops for it now.

The **change-detection assertion** (the payoff for test 4's existence)
lives at a different layer: it applies to the full time series across
many runs, and it checks that Otava identifies change points at the
expected month boundaries. That assertion can't run until the ingest
layer exists; for now, test 4 just accumulates history in the
workflow-artifact stream so the data is ready when the pipeline catches
up.

## Reference implementation: bash + `time`

The simplest possible expression of test 1 — and the user-provided starting
point for the canonical suite.

`benchmark1.sh`:

```bash
#!/bin/bash
echo "Starting benchmark1"
sleep 2.15s
echo "End of benchmark1"
```

Run under `time`:

```
$ time ./benchmark1.sh
Starting benchmark1
End of benchmark1

real    0m2.155s
user    0m0.001s
sys     0m0.001s
```

The bash `time` builtin emits `real`, `user`, `sys` to stderr in the format
above. A `time` parser captures these as three measurements (or one,
depending on convention — TBD when we write the parser).

`benchmark2.sh`:

```bash
#!/bin/bash
echo "Starting benchmark2"
for ((i=0; i<1000; i++)); do :; done
echo "End of benchmark2"
```

`benchmark3.sh`:

```bash
#!/bin/bash
echo "Starting benchmark3"
head -c 1400000 /dev/urandom > /dev/null
echo "End of benchmark3"
```

Open question: bash + `time` is a *runner*, not a *framework*. There's no
concept of "three tests grouped into a suite" — we'd run `time` against each
script separately and concatenate the outputs, or use `/usr/bin/time -o
out.txt --append` to write them to a file. We'll figure out the convention
when we get to capturing fixtures.

## Ground truth values (and why they matter)

Because the sample benchmark is fully specified — the same three tests,
the same sleep duration, the same byte count, the same loop bound, in
every framework — we know in advance, *before parsing anything*, what
each test should measure. The parser does not have to guess what numbers
in the output correspond to what physical quantities. We already know.

| Test | Expected wall time                                          | Expected CPU time | Dominated by                    |
| ---- | ----------------------------------------------------------- | ----------------- | -------------------------------- |
| 1    | ~2.15 s                                                     | ~0 s              | `sleep` syscall                  |
| 2    | sub-microsecond (compiled, optimized) to ~tens of µs (scripting) | similar to wall   | Empty loop, framework-dependent  |
| 3    | a few hundred µs to ~1 ms                                   | similar to wall   | Generating 1.4 MB of `urandom`   |

(Test 2 will be the noisiest — it's the most affected by compiler
optimization, framework warmup, and language-specific overhead. That's
fine; the value of test 2 is in *exercising* sub-millisecond
measurement, not in producing a stable number.)

This property is genuinely load-bearing for the project, in two ways:

### It makes parser correctness verifiable, not just lint-able

A parser test that only does golden-file comparison can pass even if the
parser is reading the *wrong field* — it'll happily produce structurally
identical garbage forever. A parser test that asserts *"test 1's wall
time must be between 2.0 and 2.3 seconds"* is checking that the parser
actually understands what it's reading.

Parser tests should include at least one ground-truth assertion per
sample test, e.g.:

```python
def test_pytest_benchmark_test1_wall_time():
    output = (FIXTURES / "pytest-benchmark.json").read_text()
    results = parse(output)                         # list[dict] of flat NyrkioJson
    t1 = next(r for r in results if r["attributes"]["test_name"] == "benchmark1")
    # pytest-benchmark emits mean/min/max/stddev; check the mean.
    mean = next(m for m in t1["metrics"] if m["name"] == "mean")
    assert 2.0 < mean["value"] < 2.3                # known sleep is 2.15 s
    assert mean["unit"] == "s"
    assert t1["passed"]
```

Golden-file / snapshot comparisons are still fine and recommended as a
second layer (they catch drift in the *structure* of the parsed output),
but the ground-truth assertions are the load-bearing ones — they catch
parser misreads in a way snapshot tests cannot.

### It makes the parsers themselves cheaper to write

This is the part that matters most for *who is writing the parsers*.
perf-checks expects to ship parsers for ~100 frameworks, the bulk of
which Claude will write. For each parser, the workflow is:

1. The framework's GitHub Actions workflow runs the canonical sample
   benchmark and uploads the captured native output.
2. Claude reads the captured output.
3. Claude searches for "2.15" — or "2150", "2.150e+00", "2155 ms",
   "2.15s", "2.15±0.01 s/op", or whatever flavor the format uses.
4. The field containing that number is, by construction, test 1's wall
   time. From there the units, the structure of the output, and the
   per-test layout fall out naturally — units are visible right next to
   the value, the structure is visible from the surrounding XML/JSON/text,
   and tests 2 and 3 follow the same pattern.
5. Claude writes the parser by translating that structure to Python.
6. The ground-truth assertions verify the parser is correct.

Reverse-engineering an unfamiliar benchmark output format from scratch
is significantly easier when you already know what number you're looking
for. This is the difference between "scrutinize the documentation, guess
at units, hope the framework didn't change since the docs were written"
and "grep the file." The canonical sample benchmark turns the second
mode on for every parser perf-checks ships.

## How this drives the rest of the work

For each framework in `parser-targets.md`:

1. **Implement** the three tests in the framework's idiom (pytest-benchmark,
   criterion, JMH, junit, k6, etc.).
2. **Run** them and capture the framework's native output (JSON, XML, text).
3. **Save** the output as a fixture in `tests/data/<framework>/`.
4. **Write** a parser that turns that output into our common
   `BenchmarkResult` shape.

Real captured output beats stale upstream fixtures because the suite is
identical across frameworks. We can compare apples-to-apples: every parser
should produce structurally equivalent results for the same three tests.
That's also the most honest acceptance test for the parser layer as a
whole.
