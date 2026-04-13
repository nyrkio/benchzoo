# benchmark-ips

[benchmark-ips](https://github.com/evanphx/benchmark-ips) is the
standard Ruby micro-benchmarking library. It measures *iterations per
second* (ips): it calls the benchmarked block as many times as it can
within a configured measurement window (default 5 s, trimmed to 2 s
here) and reports the throughput plus a standard deviation. A
built-in `compare!` step ranks the reports against each other.

## Links

- **Sample benchmark** — see [`bench.rb`](bench.rb)
- **Workflow** — [`.github/workflows/benchmark-ips.yml`](../../../.github/workflows/benchmark-ips.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/benchmark-ips.yml>
- **Parser (JSON)** — [`src/benchzoo/parsers/benchmark_ips_json.py`](../../../src/benchzoo/parsers/benchmark_ips_json.py) *(not yet written — pending a real captured fixture)*
- **Parser (text)** — [`src/benchzoo/parsers/benchmark_ips_text.py`](../../../src/benchzoo/parsers/benchmark_ips_text.py) *(not yet written)*
- **Parser tests** — [`tests/parsers/test_benchmark_ips.py`](../../../tests/parsers/test_benchmark_ips.py) *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
benchmark-ips idiom. Each test is a call to `x.report(label) { ... }`
inside a `Benchmark.ips do |x| ... end` block; the label (`"benchmark1"`
.. `"benchmark4"`) maps directly to `attributes["test_name"]` with no
prefix-stripping needed.

- **Test 1** (sleep 2.15 s) — `sleep(2.15)`. With the 2 s measurement
  window configured below, benchmark-ips gets roughly 1 iteration per
  window. The resulting `ips` number is small (~0.47); the parser should
  derive wall time as `1 / ips` when a seconds-per-iteration metric is
  wanted.
- **Test 2** (tight CPU loop) — `1000.times { |i| sum += i }`. Ruby is
  interpreted (MRI) with no dead-code elimination to worry about; the
  accumulator prevents any future JIT from noticing the loop is
  side-effect-free. benchmark-ips will report a high ips number here.
- **Test 3** (write 1.4 MB to /dev/null) — `SecureRandom.random_bytes`
  of 1,400,000 bytes, written to `/dev/null` opened in `"wb"` mode.
  Matches the bash reference's `head -c 1400000 /dev/urandom > /dev/null`.
- **Test 4** (monthly change point) — sleeps for
  `2.15 + ((month % 3) - 1)` seconds where `month` is the UTC month.
  Produces the step-function series described in the canonical
  sample benchmark.

### Output formats captured

The workflow captures **three** artifacts:

1. **JSON** (`output.json`) — a **hand-rolled** JSON document emitted
   by `bench.rb` itself. See *JSON caveat* below. This is the primary
   machine-readable format.
2. **Text** (`output.txt`) — the tee'd console output of benchmark-ips's
   default human-readable table plus the `compare!` ranking block.
   Common in pasted bug reports and PR descriptions; worth having a
   text-format parser for.
3. **Native dump** (`output-raw.dump`) — benchmark-ips's own
   `x.save!` output, a Ruby `Marshal` dump of its internal `Report`
   objects. Included for completeness; probably not worth writing a
   Python parser for (Marshal is Ruby-specific and not
   cross-language-safe).

All three are uploaded in the same `benchmark-ips-output` artifact.

### JSON caveat

benchmark-ips does **not** ship a stable, documented JSON output format
out of the box. Recent versions expose a `x.json!` method that writes
per-report stats, but the schema is undocumented and has changed
between versions — we did not want to tie the fixture to it.

Instead, `bench.rb` emits its own JSON after the `Benchmark.ips` block
returns, built from the public attributes of each
`Benchmark::IPS::Report::Entry`:

```json
{
  "benchmark_ips_version": "2.14.0",
  "ruby_version": "3.3.x",
  "config": { "time": 2, "warmup": 1 },
  "benchmarks": [
    {
      "name": "benchmark1",
      "ips": 0.4651,
      "ips_stddev": 0.001,
      "microseconds_per_iteration": 2150000.0,
      "seconds_per_iteration": 2.15,
      "iterations": 1
    }
  ]
}
```

This gives the parser a simple, version-stable shape to target without
having to reverse-engineer Ruby's `Marshal` format or track upstream
API drift.

## Running locally

```bash
act push -W .github/workflows/benchmark-ips.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/benchmark-ips-output/`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with a working Ruby + Bundler toolchain, run

```bash
bundle install
./run.sh
```

from this directory. That produces the same three output files without
the GitHub Actions artifact plumbing.

## Parser notes

The JSON parser consumes the hand-rolled `output.json` described above.
Recommended Nyrkiö mapping:

- `attributes["test_name"]` — the `name` field of each entry directly
  (`"benchmark1"` .. `"benchmark4"`). No prefix stripping needed; the
  benchmark-ips labels were chosen to match.
- **Headline metric: `ips`.** benchmark-ips is an iterations-per-second
  tool; its natural primary metric is throughput. Emit one `metrics`
  entry with `name: "ips"`, `unit: "ops/s"`,
  `direction: "higher_is_better"`, `value: ips`.
- **Also emit `seconds_per_iteration`** as a second metric with
  `name: "mean"` (or `"seconds_per_iteration"` — judgment call; prefer
  `"mean"` for cross-framework consistency with pytest-benchmark /
  criterion / etc.), `unit: "s"`, `direction: "lower_is_better"`,
  `value: 1.0 / ips`. This is redundant with `ips` but makes the wall
  time easy to read in a dashboard that aggregates across frameworks.
  It is also what the ground-truth assertion for test 1 needs to check
  (`2.0 < value < 2.3`); asserting directly on `ips` would require
  inverting the threshold.
- `stddev` — from `ips_stddev`, emitted with `unit: "ops/s"`,
  `direction: "lower_is_better"`.
- `iterations` — pass through into `extra_info["iterations"]` (integer;
  typed values are fine in `extra_info`). Useful for judging how stable
  the measurement is: `iterations: 1` means benchmark-ips got only a
  single call in per measurement window, which is the regime tests 1
  and 4 will be in.
- `timestamp` — set to `0` per the library contract.
- `passed` — always `true`. benchmark-ips does not have a
  pass/fail concept; if a report raises it aborts the whole run rather
  than marking that single benchmark failed.

The text parser, when written, will need to read benchmark-ips's
default pretty-printed table. A sample line looks like:

```
          benchmark1      0.470  (± 0.0%) i/s    (2.128 s/i) -      1 in   2.128016s
```

The `i/s` column is `ips`; the `s/i` column is seconds-per-iteration;
the last column is total wall time of the measurement window. Same
Nyrkiö mapping applies.

### ips vs. seconds-per-iteration

For sleep-dominated tests (1 and 4), benchmark-ips reports a small
`ips` number and a large `s/i` number — the two are reciprocals. The
*ground truth* we care about is the sleep duration (2.15 s for test 1,
one of {1.15, 2.15, 3.15} s for test 4), so the parser should surface
`seconds_per_iteration` as a first-class metric, not hide it behind a
throughput-only view. For CPU-bound test 2, the reverse is true — the
natural reading is "this ran N million times per second" — but both
metrics are emitted so downstream dashboards can pick whichever they
prefer.
