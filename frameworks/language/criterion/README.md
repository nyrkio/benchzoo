# criterion (Rust)

[criterion](https://github.com/bheisler/criterion.rs) is the de-facto
standard statistical benchmarking library for Rust. It runs each bench
many times, models the sample distribution, and emits per-bench JSON
reports with mean, median, stddev, and slope estimates plus confidence
intervals. Not to be confused with the Haskell library of the same
name — different ecosystem, different output format.

## Links

- **Sample benchmark** — [`benches/sample_benchmark.rs`](benches/sample_benchmark.rs),
  orchestrated by [`run.sh`](run.sh) (see also [`Cargo.toml`](Cargo.toml))
- **Workflow** — [`.github/workflows/criterion.yml`](../../../.github/workflows/criterion.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/criterion.yml>
- **Parser** — [`src/benchzoo/parsers/criterion.py`](../../../src/benchzoo/parsers/criterion.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_criterion.py`](../../../tests/parsers/test_criterion.py) *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
criterion idiom. Each test is registered via `c.bench_function("benchmarkN", ...)`
so the criterion output directory tree keys directly off the test
name.

- **Test 1** (sleep 2.15 s) — `thread::sleep(Duration::from_millis(2150))`
  inside the bench closure. Criterion's default `sample_size` of 100
  would mean ~215 seconds per bench, so test 1 and test 4 live in a
  dedicated `criterion_group!` with a custom config of
  `sample_size(10)` — the criterion minimum. This trades wider
  confidence intervals for sane CI runtime, which is fine here because
  the sleep is deterministic and the parser layer does not care about
  statistical tightness.
- **Test 2** (tight CPU loop) — `for i in 0..1000u32 { black_box(i); }`.
  `std::hint::black_box` is **mandatory**: rustc will otherwise delete
  the entire loop as dead code. This is exactly the case
  [`docs/sample-benchmark.md`](../../../docs/sample-benchmark.md#test-2--tight-cpu-loop-sub-millisecond)
  calls out in its "Note on optimization."
- **Test 3** (write 1.4 MB to /dev/null) — allocates a
  `vec![0u8; 1_400_000]` and writes it to `std::io::sink()` inside the
  bench closure. `std::io::sink()` is portable and avoids opening
  `/dev/null` by path; since the sample-benchmark spec explicitly notes
  `/dev/null` is a proxy for "cheap deterministic write" and not a real
  I/O test, this substitution is consistent with the spec. The buffer
  is zero-filled rather than pseudo-random to keep dev-dependencies
  minimal — `sink()` discards its input without inspecting it, so the
  byte values are immaterial.
- **Test 4** (monthly change point) — reads the current UTC month via
  `chrono::Utc::now().month()`, computes `2.15 + ((m mod 3) - 1)`, and
  `thread::sleep`s for that many seconds. chrono is a dev-dependency
  because Rust's stdlib has no calendar math; doing epoch-to-month by
  hand would be noticeably uglier than one import.

The two sleep-heavy benches (1 and 4) share a `sleepy` group with
`sample_size(10)`; the two fast benches (2 and 3) live in a default
`fast` group. `criterion_main!(fast, sleepy)` wires them together so a
single `cargo bench --bench sample_benchmark` runs all four.

The orchestration lives in [`run.sh`](run.sh), which invokes
`cargo bench` twice: once normally (capturing
`target/criterion/<bench>/new/estimates.json` into `./output/<bench>.json`
for each of the four benches) and once with `-- --output-format bencher`
to produce `output-bencher.txt` in the libtest/bencher text format.
Keeping the cargo invocations in a shell script (rather than inline in
the workflow YAML) makes it easy to iterate locally via `act` or a
direct `./run.sh`.

## Running locally

```bash
act push -W .github/workflows/criterion.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/criterion-output/` as four JSON files
(`benchmark1.json` .. `benchmark4.json`) plus `output-bencher.txt`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with a Rust toolchain installed locally, you can bypass
`act` entirely and just run `./run.sh` from this directory. That
produces the same `./output/` directory but without the GitHub Actions
artifact plumbing. The first run is slow (cold cargo build of criterion
and its dependencies); subsequent runs reuse `target/`.

## Parser notes

criterion's native output is a directory tree under
`target/criterion/<bench_name>/{new,base,change}/...`. The richest
single file per bench is `new/estimates.json`, which is what we
capture (as `output/<bench_name>.json`). We also capture the bencher
text format via `cargo bench -- --output-format bencher` into
`output-bencher.txt`. The fork at `nyrkio/change-detection` had a
criterion parser that read `estimates.json` — reference-only, benchzoo
does not import from it.

### Output file shape

Each `estimates.json` holds four top-level entries — `mean`, `median`,
`std_dev`, `slope` — and each of those is a dict with:

- `point_estimate` — the central estimate, as a plain f64.
- `standard_error` — the standard error of the bootstrap resampling.
- `confidence_interval` — a dict with `confidence_level`,
  `lower_bound`, `upper_bound`.

**Units: raw nanoseconds as f64.** criterion stores everything in ns
internally and that's what lands in the JSON. The parser should emit
metrics with `unit: "ns"` (matching the wire-level convention the fork
used) rather than converting to seconds — any downstream consumer that
wants seconds can divide by 1e9 at the edge.

### Bencher text format (`output-bencher.txt`)

The second output is the bencher/libtest text format, one line per
benchmark:

```
test benchmark1 ... bench:  2150000000 ns/iter (+/- 1234)
test benchmark2 ... bench:        1234 ns/iter (+/- 56)
test benchmark3 ... bench:      567890 ns/iter (+/- 789)
test benchmark4 ... bench:  2150000000 ns/iter (+/- 4567)
```

Each line follows the pattern `test <name> ... bench: <ns> ns/iter (+/- <stddev>)`.
Values are integer-rounded nanoseconds. This is the same format produced
by `cargo bench` (libtest) which is listed as a separate `[fork]` target
in [`parser-targets.md`](../../../docs/parser-targets.md). Since the
wire format is identical, the parser for bencher text can potentially be
shared between criterion's `--output-format bencher` and native
`cargo bench` (libtest) output.

Compared to `estimates.json`, the bencher text format is lossy: it only
reports median and standard deviation, integer-rounded, with no
confidence intervals or slope estimates.

### Metric mapping

Minimum viable parse: one metric each for `mean`, `median`, `std_dev`,
all drawn from `point_estimate`, all with:

- `unit: "ns"`
- `direction: "lower_is_better"` (every value criterion reports for a
  duration bench is a wall time, lower is better)

`attributes["test_name"]` comes from the filename (`benchmark1` ..
`benchmark4`) or equivalently from the `target/criterion/<name>/`
directory segment — both are keyed off the string passed to
`c.bench_function` in
[`benches/sample_benchmark.rs`](benches/sample_benchmark.rs).

### black_box rationale for test 2

Without `std::hint::black_box`, the bench body
`for i in 0..1000u32 {}` is dead code that rustc deletes entirely. The
bench would then measure "nothing at all, once per iteration" — a
pathological sub-nanosecond number. `black_box(i)` forces the compiler
to treat `i` as observed and keep the loop intact. Parsers don't have
to handle this, but anyone looking at test 2's numbers and wondering
why they're "only" a few nanoseconds (rather than picoseconds) should
know the loop is really running.

### sample_size reduction for tests 1 and 4

Criterion's default `sample_size` is 100. For a bench whose single
iteration takes ~2.15 s, that's ~215 s of measurement plus warmup per
bench — roughly 8 minutes of CI time for the two sleep-heavy benches
alone. `sleepy_config()` overrides this to `sample_size(10)` (the
criterion minimum), bringing each sleep-heavy bench to ~22 s. The
tradeoff — noisier mean and wider confidence intervals — is
irrelevant here because the sleep is deterministic and parser tests
only need the ground-truth range `2.0 < mean < 2.3` anyway.

### Pass/fail

criterion does not have a first-class notion of "this bench failed."
A panic in the bench closure aborts the run and no `estimates.json` is
written. For the canonical sample benchmark, treat successful parse of
the JSON as `passed: true`. If a downstream parser wants to detect
partial runs (only 3 of 4 files present), that's a
higher-level concern — benchzoo's parser contract is still "parse what
you see and surface it."
