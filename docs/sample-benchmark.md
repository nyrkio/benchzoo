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
