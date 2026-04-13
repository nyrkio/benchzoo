# wrk2

[wrk2](https://github.com/giltene/wrk2) is Gil Tene's fork of
[wrk](https://github.com/wg/wrk) that adds two things the original
does not have: a `-R<rate>` **constant-throughput** mode that corrects
for [coordinated omission](https://www.scylladb.com/2021/04/22/on-coordinated-omission/),
and HDR-histogram-derived latency output with extended percentiles
(p99.9, p99.99, p99.999, p99.9999, p100). Its text report is a
*superset* of wrk's — everything a wrk parser handles, wrk2 also emits
in the same format, plus additional percentile rows. wrk2 is
commonly cited in research papers comparing load-testing
methodologies because its numbers are not distorted by the classic
open/closed-loop measurement bug.

## Links

- **Sample benchmark** — a minimal static page ([`index.html`](index.html))
  served by [`nginx.conf`](nginx.conf), load-tested by [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/wrk2.yml`](../../../.github/workflows/wrk2.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/wrk2.yml>
- **Parser** — *(not yet written — pending a real captured fixture)*
- **Parser tests** — *(not yet written)*

## Sample benchmark

wrk2, like wrk, does not fit the
[canonical sample benchmark](../../../docs/sample-benchmark.md)
cleanly. The canonical suite was designed for frameworks that time
arbitrary code (a sleep, a CPU loop, an I/O write). wrk2 is a load
generator: a single invocation measures one HTTP endpoint's behavior
under a sustained, rate-controlled concurrent load, and the latency
numbers are emergent properties of nginx + the kernel's TCP stack +
the runner's CPU and scheduling — not a quantity under our control.

So the adaptation is explicit and honest: **one test run, not four.**
This mirrors the deviation already taken by the
[`wrk`](../wrk/) and [`lighthouse`](../../frontend/lighthouse/)
frameworks, which had the same structural mismatch.

- **Test 1** (sleep 2.15 s) — **dropped.** wrk2 does not measure
  arbitrary sleep; it measures HTTP request latency under load.
- **Test 2** (tight CPU loop, sub-ms) — **dropped.** HTTP request
  latencies over loopback run in the tens-to-hundreds of microseconds
  range, not sub-microsecond.
- **Test 3** (write 1.4 MB to /dev/null) — **dropped.** wrk2 reports
  a transfer rate in bytes/sec, but these are emergent from load-test
  duration and nginx's response size; we don't control them precisely
  enough to assert on a 1,400,000-byte value.
- **Test 4** (monthly change point) — **dropped.** Test 4 requires
  the measured quantity to be under our control so we can produce a
  deterministic monthly step function. wrk2's numbers depend on the
  runner and cannot be shaped into `2.15 + ((m mod 3) - 1)`. There
  is therefore no `schedule:` trigger on this workflow: it runs on
  push/PR and manual dispatch only.

What the framework *does* run is a single wrk2 invocation against a
single static nginx endpoint:

```
wrk2 -t2 -c10 -d5s -R1000 --latency http://localhost:8080/
```

That is: 2 threads, 10 open connections, 5 second duration, **1000
req/s constant throughput target**, with the `--latency` flag to
force wrk2 to print its extended HDR-histogram-derived percentile
distribution. 1000 req/s is deliberately low — on a shared CI runner
we want to stay well under saturation so the measured latencies
reflect the stack's behavior at a sustainable rate rather than under
overload. We treat the whole run as one test with
`attributes["test_name"] = "homepage"`.

The page, nginx config, and orchestration logic are identical to the
[`wrk`](../wrk/) framework — see that README for the rationale behind
the tiny static `index.html`, the `-p $(pwd) -c nginx.conf` nginx
invocation, the `trap`-and-kill cleanup, and the curl readiness loop.
The only substantive difference is the `wrk2` binary and the `-R1000`
flag.

## Running locally

```bash
act push -W .github/workflows/wrk2.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/wrk2-output/output.txt`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

wrk2 is **not packaged in Ubuntu's apt repos**, so a local run
outside `act` requires building from source — see the
*Building wrk2* section below for the commands the workflow uses.

## Parser notes

wrk2 emits a single, stable text report — no JSON, no CSV, no machine
format. Parsing is line-oriented string matching against a format
that is a **superset of wrk's**: a parser written against wrk's
output will already recognize most of wrk2's lines; only the
extended percentile table differs.

### The wrk2 text output

A typical `-R1000 --latency` run looks like:

```
Running 5s test @ http://localhost:8080/
  2 threads and 10 connections
  Thread calibration: mean lat.: 1.234ms, rate sampling interval: 10ms
  Thread calibration: mean lat.: 1.198ms, rate sampling interval: 10ms
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency     1.23ms    0.45ms   12.34ms   78.90%
    Req/Sec   502.34     45.12   600.00     65.12%
  Latency Distribution (HdrHistogram - Recorded Latency)
 50.000%    1.10ms
 75.000%    1.40ms
 90.000%    1.80ms
 99.000%    3.20ms
 99.900%    6.50ms
 99.990%   11.20ms
 99.999%   12.10ms
 99.9999%  12.30ms
100.000%   12.34ms
  4998 requests in 5.00s, 4.10MB read
Requests/sec:    999.60
Transfer/sec:    839.20KB
```

Differences from wrk's output the parser must handle:

- **`Thread calibration:` lines** (zero or more, one per thread) —
  wrk2 prints these during its startup phase while it measures
  baseline latency to calibrate the rate sampler. They appear *before*
  the `Thread Stats` header. A parser written for wrk will see them
  as noise and must skip them (or optionally capture them into
  `extra_info`).
- **Section header** — wrk writes `Latency Distribution`; wrk2 writes
  `Latency Distribution (HdrHistogram - Recorded Latency)`. A wrk
  parser matching the exact string will miss this; match a prefix or
  a regex like `^\s*Latency Distribution`.
- **Percentile list** — wrk prints four rows (`50%`, `75%`, `90%`,
  `99%`) with three decimal digits of the value. wrk2 prints at
  least *nine* rows (`50.000%`, `75.000%`, `90.000%`, `99.000%`,
  `99.900%`, `99.990%`, `99.999%`, `99.9999%`, `100.000%`) with the
  percentile itself carrying the extra decimal digits. A parser must
  (a) accept the longer percentile formatting (`99.9999%` has four
  digits after the point), (b) not assume a fixed row count, and
  (c) emit matching metric names (`p50`, `p99`, `p999`, `p9999`,
  `p99999`, `p999999`, `p100` — the exact naming convention is the
  parser author's call).
- **`--latency-percentiles`** — if passed (we do **not** pass it here
  to keep output small), wrk2 additionally emits a many-hundred-line
  "Detailed Percentile spectrum" table with raw histogram buckets. A
  parser aimed at our captured output can ignore this section; a
  parser aimed at arbitrary user-supplied wrk2 output may need to
  recognize and skip it.

The rest of the fields — `Thread Stats` → `Latency` / `Req/Sec`, the
`N requests in Ds, Xmb read` summary line, `Requests/sec:`,
`Transfer/sec:` — are formatted identically to wrk and can reuse the
same parsing logic.

### Recommended parser shape

Same as [wrk](../wrk/README.md#recommended-parser-shape), plus
extended percentile metrics derived from the HDR histogram section
(`p999`, `p9999`, `p99999`, `p999999`, `p100`). Emit one Nyrkiö
test-result dict with `attributes["test_name"] = "homepage"`,
`timestamp: 0`, and populate `extra_info` with `url`,
`duration_sec`, `threads`, `connections`, and the target
`throughput_rate` (1000 from `-R1000`).

### Unit-suffix parsing

Identical to wrk — times use `us`/`ms`/`s`, bytes use `B`/`KB`/`MB`/`GB`
(decimal), counts use `k`/`M` suffixes. See
[wrk's README](../wrk/README.md#unit-suffix-parsing) for the detail.

### Ground-truth assertions

Like wrk, wrk2's measurements are **not** fixed quantities. Parser
tests must use **loose** assertions — presence-of-key and
plausible-range rather than tight numeric bounds. The target rate
`-R1000` does give one soft check: `requests_per_sec` should be
close to 1000 (say, within ±10%) in a non-overloaded run, since
wrk2 actively paces to that rate.

### Failure mode

Same as wrk: no `Requests/sec:` line → `passed: false`. wrk2 also
has a specific failure mode where the server cannot keep up with the
requested rate — this manifests as the actual `Requests/sec:` being
materially below the target `-R` rate, rather than as a non-zero
exit. A parser could optionally flag this, but it is not a parse
failure.

### Relationship to the fork

The predecessor TypeScript project at
[`nyrkio/change-detection`](https://github.com/nyrkio/change-detection)
did not have a wrk or wrk2 parser. This is a clean-slate
implementation.

## Building wrk2

wrk2 is not in apt and has **no git tags or releases** — upstream
development is effectively frozen at a handful of commits. The
workflow pins a specific commit hash
(`44a94c17d8e6a0bac8559b53da76848e430cb7a7`) and builds from source:

```bash
sudo apt-get install -y build-essential libssl-dev libz-dev
git clone https://github.com/giltene/wrk2.git
cd wrk2
git checkout 44a94c17d8e6a0bac8559b53da76848e430cb7a7
make
sudo cp wrk /usr/local/bin/wrk2
```

The upstream binary is named `wrk` (not `wrk2`); we rename it to
`wrk2` on install so it coexists with any system `wrk` package and
so `run.sh` invocations are self-documenting. The build is fast
(a few seconds on a modern runner) and has no runtime dependencies
beyond openssl and zlib.
