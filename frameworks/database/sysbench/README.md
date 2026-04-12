# sysbench

[sysbench](https://github.com/akopytov/sysbench) is a classic
multi-purpose benchmark tool best known for its OLTP MySQL/PostgreSQL
workloads, but also shipping built-in `cpu`, `memory`, `fileio`,
`mutex`, and `threads` tests and -- most importantly for this corpus --
a Lua scripting mode that lets you define `event()` and have sysbench
drive it in a loop, collecting per-event latency statistics.

## Links

- **Sample benchmark** — [`benchmark1.lua`](benchmark1.lua),
  [`benchmark2.lua`](benchmark2.lua), [`benchmark3.lua`](benchmark3.lua),
  [`benchmark4.lua`](benchmark4.lua), orchestrated by [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/sysbench.yml`](../../../.github/workflows/sysbench.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/sysbench.yml>
- **Parser** — [`src/benchzoo/parsers/sysbench.py`](../../../src/benchzoo/parsers/sysbench.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_sysbench.py`](../../../tests/parsers/test_sysbench.py) *(not yet written)*

## Sample benchmark

Implementation of the
[canonical sample benchmark](../../../docs/sample-benchmark.md) in
sysbench idiom:

- **Test 1** (sleep 2.15 s) — [`benchmark1.lua`](benchmark1.lua)
  defines `event()` as `os.execute("sleep 2.15")`. Lua has no portable
  sub-second sleep in its standard library and we don't want to depend
  on luasocket or an FFI binding, so shelling out to GNU coreutils
  `sleep` (which accepts fractional seconds) is the simplest portable
  choice.
- **Test 2** (tight CPU loop) — [`benchmark2.lua`](benchmark2.lua)
  defines `event()` as `for i = 1, 1000 do end`. Lua is interpreted, so
  the loop is not optimized away and no `black_box` equivalent is
  needed.
- **Test 3** (write 1.4 MB to /dev/null) —
  [`benchmark3.lua`](benchmark3.lua) opens `/dev/null`, writes a
  1,400,000-byte constant string, and closes the handle.
- **Test 4** (monthly change point) —
  [`benchmark4.lua`](benchmark4.lua) computes `m` via
  `tonumber(os.date("!%m"))` (the `!` forces UTC, `%m` is the 2-digit
  month), evaluates `2.15 + (m % 3) - 1`, and shells out to `sleep`
  with the result.

The orchestration lives in [`run.sh`](run.sh). sysbench runs exactly
one Lua script per invocation, so `run.sh` calls sysbench four times --
once per `benchmarkN.lua` -- emitting a `=== benchmarkN ===` separator
before each block and concatenating everything to `output.txt`. With
`--events=1 --threads=1`, each invocation calls `event()` exactly once
and reports the single-event latency in the "Latency" block, so total
wall time is bounded by the slowest test (benchmark4 in the 3.15 s
months): worst case around 6 seconds for the full run.

We use **custom Lua scripts**, not sysbench's built-in `cpu`, `memory`,
or `fileio` tests, because the canonical sample benchmark's four tests
map cleanly onto four custom `event()` definitions. The built-in tests
have their own opinionated workload shapes that don't line up with
"sleep 2.15 s" or "write exactly 1.4 MB once."

The **OLTP database-facing tests** (`oltp_read_only`, `oltp_read_write`,
`oltp_write_only` and friends) are sysbench's headline use case but are
a separate, future concern. Running them requires a MySQL or PostgreSQL
service container, schema prep (`sysbench ... prepare`), and a
meaningful workload size -- all of which are natural for sysbench's
"real" role but wrong for a parser-corpus benchmark. Flagged as future
work; a second `frameworks/database/sysbench-oltp/` directory with a
MySQL service container is the likely home for it.

## Running locally

```bash
act push -W .github/workflows/sysbench.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/sysbench-output/output.txt`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with sysbench installed locally
(`sudo apt-get install sysbench`), you can bypass `act` entirely and
just run `./run.sh` from this directory. That produces the same
`output.txt` but without the GitHub Actions artifact plumbing.

## Parser notes

sysbench's default output is plain text, structured as a header
(version, options), a "General statistics" block, and a "Latency"
block. The interesting lines for a parser running against the
canonical sample benchmark are:

- `Total time: 2.1534s` (in "General statistics") — wall clock for the
  whole invocation.
- `Total number of events: 1` — how many times `event()` ran. With
  `--events=1` this is always 1 and the latency stats describe a
  single data point.
- Latency block:
  - `min:                                    X.XX` (ms)
  - `avg:                                    Y.YY` (ms)
  - `max:                                    Z.ZZ` (ms)
  - `95th percentile:                        W.WW` (ms)
  - `sum:                                    S.SS` (ms)
- A "Threads fairness" block (events/thread and execution-time/thread)
  -- not usually interesting for a single-threaded, single-event run
  and can be ignored by the parser.

The parser should emit `latency_min`, `latency_avg`, `latency_max`,
`latency_p95`, and `total_time` as `metrics[]` entries, all
`lower_is_better`. Units are as reported by sysbench: the latency block
is `"ms"` and `Total time` is `"s"`. Don't silently convert between
them -- parser tests assert the unit alongside the value.

### Single-event caveats

With `--events=1`, the latency min/avg/max/p95 are all computed from
the same single measurement, so they'll all be equal (and the "95th
percentile" is a degenerate summary of a one-element set). That's
expected. The parser should still emit all four, because on a future
run with `--events=N` they'll diverge and the parser shape should be
the same. The corpus is about wall-clock ground truth for one event;
statistics across many events are a separate concern.

Note also that `Total time` includes sysbench's own startup and
teardown, so for benchmark1 it will be slightly larger than 2.15 s,
and the latency `avg` will be closer to 2.15 s than `Total time` is.
The ground-truth assertion (`2.0 < t < 2.3`) should key off the
latency `avg` or `sum`, not `Total time`.

### Double-counting concern for os.execute sleeps

`os.execute("sleep 2.15")` shells out, so for benchmarks 1 and 4 the
event latency sysbench reports includes the sleep itself **plus** the
`fork()`+`exec()` of `/bin/sleep`. On a typical Linux runner this
overhead is a few milliseconds on top of the wall-clock sleep --
comfortably inside the `2.0 < t < 2.3` tolerance. If this ever becomes
a problem we can switch to a sysbench-internal sleep helper or an FFI
`nanosleep` binding, but the portability gain isn't worth it yet.

### Output split

Because we run sysbench four separate times, `output.txt` contains
four complete sysbench reports back-to-back. `run.sh` emits a
`=== benchmarkN ===` line before each block so the parser can split on
that marker and map each block to `attributes["test_name"] = "benchmarkN"`.
Everything after a marker and before the next marker (or EOF) is that
test's own sysbench output, parseable as a standalone report.

### Fork provenance

The fork at [`nyrkio/change-detection`][fork] did not ship a sysbench
parser (sysbench is not in the fork's supported-tools list, and is
**not** tagged `[fork]` in
[`parser-targets.md`](../../../docs/parser-targets.md)). Clean slate:
no upstream parser to crib from, no stale fixtures, no prior shape to
match.

[fork]: https://github.com/nyrkio/change-detection
