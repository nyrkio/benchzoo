# cargo bench (libtest)

Rust's original built-in benchmarking harness, accessed via the
unstable `test` crate (`#[bench]` attribute, `test::Bencher`). Predates
[criterion](../criterion/) and is still used in parts of the Rust
ecosystem — notably rustc's own benchmark suite — where pulling in
criterion is overkill.

> **Nightly Rust required.** `#[bench]`, `#![feature(test)]`, and
> `extern crate test;` are all unstable. A stable compiler cannot build
> this crate. The nightly version is pinned in
> [`rust-toolchain.toml`](rust-toolchain.toml).

## Links

- **Sample benchmark** — [`benches/sample_benchmark.rs`](benches/sample_benchmark.rs),
  orchestrated by [`run.sh`](run.sh) (see also [`Cargo.toml`](Cargo.toml)
  and [`rust-toolchain.toml`](rust-toolchain.toml))
- **Workflow** — [`.github/workflows/cargo-bench.yml`](../../../.github/workflows/cargo-bench.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/cargo-bench.yml>
- **Parser** — [`src/benchzoo/parsers/cargo_bench_libtest.py`](../../../src/benchzoo/parsers/cargo_bench_libtest.py)
  *(not yet written — will reuse criterion_bencher's text-format parser;
  see Parser notes below)*
- **Parser tests** — [`tests/parsers/test_cargo_bench_libtest.py`](../../../tests/parsers/test_cargo_bench_libtest.py)
  *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
libtest idiom. Each test is a top-level `#[bench]` fn whose name
(`benchmark1` .. `benchmark4`) is what cargo prints in the output, and
which the parser maps directly to `attributes["test_name"]`.

- **Test 1** (sleep 2.15 s) — `thread::sleep(Duration::from_millis(2150))`
  inside `b.iter(|| ...)`. libtest's `Bencher` is designed for
  microbenchmarks: it picks the iteration count adaptively so a single
  measurement run takes ~1 s. For a 2.15 s closure that means
  effectively one sample; the reported `ns/iter` will be
  ~2_150_000_000 but with a large `+/-` deviation because there's no
  sample spread. This is an accepted libtest limitation — unlike
  criterion, libtest exposes no `sample_size` knob. For parser testing
  the single-sample reading is fine: the ground-truth assertion is
  still `2.0 s < value < 2.3 s`.
- **Test 2** (tight CPU loop) — `for i in 0..1000u32 { test::black_box(i); }`.
  `test::black_box` is libtest's "don't optimize this away" primitive;
  it's semantically identical to `std::hint::black_box` but re-exported
  via the unstable `test` crate. Without it, rustc deletes the empty
  loop entirely. This is exactly the case
  [`docs/sample-benchmark.md`](../../../docs/sample-benchmark.md#test-2--tight-cpu-loop-sub-millisecond)
  calls out in its "Note on optimization."
- **Test 3** (write 1.4 MB to /dev/null) — allocates a
  `vec![0u8; 1_400_000]` and writes it to `std::io::sink()` inside
  `b.iter`. Same rationale as the criterion sibling: `sink()` is
  portable and discards its input without inspecting it, so the byte
  values are immaterial.
- **Test 4** (monthly change point) — reads the current UTC month via
  `chrono::Utc::now().month()`, computes `2.15 + ((m mod 3) - 1)`, and
  `thread::sleep`s for that many seconds. Same single-sample caveat as
  test 1: libtest runs it effectively once per invocation.

Orchestration lives in [`run.sh`](run.sh), which just runs
`cargo +nightly bench` and captures stdout+stderr into `output.txt`.
No multi-format capture — libtest emits exactly one format (the
bencher text lines on stdout).

## Running locally

```bash
act push -W .github/workflows/cargo-bench.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/cargo-bench-output/output.txt`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with a nightly Rust toolchain installed locally (rustup
will pick up [`rust-toolchain.toml`](rust-toolchain.toml) automatically),
you can bypass `act` entirely and just run `./run.sh` from this
directory. First run is slow (cold cargo build of `chrono` plus the
nightly stdlib); subsequent runs reuse `target/`.

## Parser notes

The output format is **byte-identical** to criterion's
`--output-format bencher` — one line per benchmark:

```
test benchmark1 ... bench:  2150000000 ns/iter (+/- 1234)
test benchmark2 ... bench:        1234 ns/iter (+/- 56)
test benchmark3 ... bench:      567890 ns/iter (+/- 789)
test benchmark4 ... bench:  2150000000 ns/iter (+/- 4567)
```

Values are integer-rounded nanoseconds; the `+/-` value is the
deviation libtest reports alongside the median.

Because the format is identical, the eventual
`src/benchzoo/parsers/cargo_bench_libtest.py` parser can be a
one-line delegator to
[`criterion_bencher.parse()`](../../../src/benchzoo/parsers/criterion_bencher.py):

```python
from benchzoo.parsers.criterion_bencher import parse
```

We still ship it as a separate module for discoverability: a user
searching for "cargo bench" or "libtest" in the parsers directory
should find something, rather than having to know that criterion's
bencher output happens to share the format. The two are different
*frameworks* even though they share a wire format.

### Surrounding output

libtest's output is not pure bench lines — cargo prints compilation
progress, the `running N tests` header, and the `test result: ok. ...`
summary. The parser (shared with criterion_bencher) already filters by
matching the `test <name> ... bench:` regex, so everything else is
harmless noise.

### Single-sample quality caveat

As noted in the Test 1 / Test 4 descriptions above, libtest effectively
runs sleep-dominated benches once per invocation, so the `+/-` deviation
on those lines is a one-sample artifact rather than a meaningful
standard deviation. Parsers should treat the deviation field as
informational and not read statistical confidence into it.

### Pass/fail

libtest doesn't have a separate "bench failed" state for benches that
complete; a panic inside `b.iter` aborts the test and no line is emitted
for that bench. For the canonical sample benchmark, treat the presence
of a `test <name> ... bench:` line as `passed: true`.

### Nightly drift

`#[bench]` has been nightly-only for the entire life of Rust and shows
no sign of stabilizing. That means whenever we bump the pinned nightly
in [`rust-toolchain.toml`](rust-toolchain.toml), the output format
could in principle change — it rarely has in practice, but it's worth
being aware of when reviewing a PR that bumps the nightly date and the
captured `output.txt` changes shape.
