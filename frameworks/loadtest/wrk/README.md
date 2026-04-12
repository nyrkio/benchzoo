# wrk

[wrk](https://github.com/wg/wrk) is Will Glozer's modern HTTP
benchmarking tool. It drives a configurable number of threads and
open connections at an HTTP endpoint for a configurable duration and
reports requests per second, transfer rate, and a latency distribution
(p50/p75/p90/p99). It is the de-facto baseline for HTTP benchmarking
in research papers and remains widely used despite being unchanged
for years — its output format is effectively a stable standard. Its
sibling [wrk2](https://github.com/giltene/wrk2) adds constant-throughput
mode and HDR histograms; see *Considered but not adopted* below.

## Links

- **Sample benchmark** — a minimal static page ([`index.html`](index.html))
  served by [`nginx.conf`](nginx.conf), load-tested by [`run.sh`](run.sh)
- **Workflow** — [`.github/workflows/wrk.yml`](../../../.github/workflows/wrk.yml)
- **Live run history** —
  <https://github.com/nyrkio/benchzoo/actions/workflows/wrk.yml>
- **Parser** — [`src/benchzoo/parsers/wrk.py`](../../../src/benchzoo/parsers/wrk.py) *(not yet written — pending a real captured fixture)*
- **Parser tests** — [`tests/parsers/test_wrk.py`](../../../tests/parsers/test_wrk.py) *(not yet written)*

## Sample benchmark

wrk does not fit the
[canonical sample benchmark](../../../docs/sample-benchmark.md) cleanly.
The canonical suite was designed for frameworks that time arbitrary
code (a sleep, a CPU loop, an I/O write), and the four tests exist to
stress-test parsers across very different magnitudes. wrk is a
fundamentally different kind of tool: a single invocation measures
one HTTP endpoint's behavior under sustained concurrent load, and the
latency numbers are emergent properties of nginx + the kernel's TCP
stack + the runner's CPU and scheduling — not a quantity under our
control. Trying to shoehorn `sleep 2.15` into a p99 latency is
nonsensical.

So the adaptation is explicit and honest: **one test run, not four.**
This mirrors the deviation already taken by the
[`lighthouse`](../../frontend/lighthouse/) framework, which had the
same structural mismatch.

- **Test 1** (sleep 2.15 s) — **dropped.** wrk does not measure
  arbitrary sleep; it measures HTTP request latency under load. There
  is no corresponding invocation.
- **Test 2** (tight CPU loop, sub-ms) — **dropped.** HTTP request
  latencies over loopback run in the tens-to-hundreds of microseconds
  range, not sub-microsecond. There is no sub-ms metric to exercise
  in wrk's output.
- **Test 3** (write 1.4 MB to /dev/null) — **dropped.** wrk reports a
  transfer rate in bytes/sec and a total bytes-transferred count, but
  these are emergent from the load test duration and nginx's response
  size; we don't control them precisely enough to assert on a
  1,400,000-byte value.
- **Test 4** (monthly change point) — **dropped.** Test 4 requires
  the measured quantity to be under our control so we can produce a
  deterministic monthly step function. wrk's numbers depend on the
  runner and cannot be shaped into `2.15 + ((m mod 3) - 1)`. There
  is therefore no `schedule:` trigger on this workflow: it runs on
  push/PR and manual dispatch only.

What the framework *does* run is a single wrk invocation against a
single static nginx endpoint:

```
wrk -t2 -c10 -d5s --latency http://localhost:8080/
```

That is: 2 threads, 10 open connections, 5 second duration, with the
`--latency` flag to force wrk to print the per-percentile latency
distribution table. We treat the whole run as one test with
`attributes["test_name"] = "homepage"`, and emit every headline
number wrk reports — latency percentiles, requests/sec, transfer/sec
— as separate entries in `metrics[]`.

The page itself ([`index.html`](index.html)) is deliberately small —
a few hundred lines of static HTML with inline CSS — so nginx's
sendfile path does the work and wrk's response-body parsing is not
the bottleneck. No external assets, no scripts, no cookies:
everything wrk sees is committed in this directory.

The orchestration lives in [`run.sh`](run.sh), which:

1. Starts `nginx -p $(pwd) -c nginx.conf` in the foreground,
   backgrounded by `&`, so it uses the local directory for its pid
   file, error log, and temp directories (no `sudo`, no
   `/var/lib/nginx`).
2. `trap`s a kill on the nginx PID so it goes away on any exit.
3. Waits a moment with a `curl` loop for nginx to bind.
4. Runs `wrk -t2 -c10 -d5s --latency http://localhost:8080/` and
   redirects both stdout and stderr to `output.txt`.

## Running locally

```bash
act push -W .github/workflows/wrk.yml \
    --artifact-server-path /tmp/benchzoo-artifacts
```

Captured output lands at
`/tmp/benchzoo-artifacts/<run-id>/wrk-output/output.txt`. See
[`workflow-conventions.md`](../../../docs/workflow-conventions.md#running-workflows-locally-with-act)
for the full `act` convention.

Alternatively, with `wrk` and `nginx` installed locally
(`apt install wrk nginx`), you can bypass `act` entirely and just run
`./run.sh` from this directory. That produces the same `output.txt`
without the GitHub Actions artifact plumbing.

## Parser notes

wrk emits a single, stable text report — no JSON, no CSV, no machine
format. Parsing is line-oriented string matching against a format
that has been effectively unchanged for years.

### The wrk text output

A typical `--latency` run looks like:

```
Running 5s test @ http://localhost:8080/
  2 threads and 10 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency   201.32us  112.45us   8.23ms   92.14%
    Req/Sec    24.13k     1.82k   28.91k    75.50%
  Latency Distribution
     50%  180.00us
     75%  230.00us
     90%  310.00us
     99%  620.00us
  241234 requests in 5.00s, 198.12MB read
Requests/sec:  48246.80
Transfer/sec:     39.62MB
```

Key fields a parser pulls out:

- **Header line** — `Running 5s test @ <url>` gives the test
  duration and target URL. The URL is useful context for
  `extra_info`; the duration is confirmed below anyway.
- **Thread Stats / Latency** — per-thread latency stats. The values
  are formatted with unit suffixes (`us`, `ms`, `s`) and the parser
  must convert to a canonical unit (microseconds is the natural
  choice — wrk's finest resolution — but milliseconds is also
  reasonable). `Avg` and `Stdev` and `Max` are the three useful
  fields; the `+/- Stdev` percentage is the fraction of samples
  within one stddev of the mean, which is informational.
- **Thread Stats / Req/Sec** — per-thread request-rate stats. Same
  unit convention (`k` suffix = ×1000). Less useful than the
  aggregate `Requests/sec` line near the bottom, but worth capturing.
- **Latency Distribution** — only present when `--latency` was
  passed. Four lines: `50%`, `75%`, `90%`, `99%`, each with a value
  and unit suffix. This is the richest output wrk produces and is
  the primary parser target.
- **Summary line** — `<N> requests in <duration>, <bytes> read`. The
  total request count and total bytes transferred are exact integers
  (well, the bytes are formatted with a decimal `MB`/`GB` suffix).
- **Requests/sec** — the aggregate RPS across all threads. This is
  the single most important number for most consumers.
- **Transfer/sec** — aggregate bandwidth, with a unit suffix
  (`KB`/`MB`/`GB`).

### Recommended parser shape

Emit one Nyrkiö test-result dict with `attributes["test_name"] =
"homepage"` and the following metrics (unit conversions shown,
direction in parentheses):

| Metric name          | Source                                | Unit     | Direction          |
| -------------------- | ------------------------------------- | -------- | ------------------ |
| `latency_avg`        | Thread Stats → Latency → Avg          | `us`     | `lower_is_better`  |
| `latency_stdev`      | Thread Stats → Latency → Stdev        | `us`     | `lower_is_better`  |
| `latency_max`        | Thread Stats → Latency → Max          | `us`     | `lower_is_better`  |
| `p50`                | Latency Distribution → 50%            | `us`     | `lower_is_better`  |
| `p75`                | Latency Distribution → 75%            | `us`     | `lower_is_better`  |
| `p90`                | Latency Distribution → 90%            | `us`     | `lower_is_better`  |
| `p99`                | Latency Distribution → 99%            | `us`     | `lower_is_better`  |
| `requests_per_sec`   | `Requests/sec:` line                  | `ops/s`  | `higher_is_better` |
| `transfer_per_sec`   | `Transfer/sec:` line                  | `bytes/s`| `higher_is_better` |
| `total_requests`     | summary line total                    | `count`  | `higher_is_better` |
| `total_bytes`        | summary line total                    | `bytes`  | informational      |

Populate `extra_info` with `url`, `duration_sec`, `threads`,
`connections` pulled from the header lines. Leave `timestamp: 0` per
the parser contract.

### Unit-suffix parsing

wrk's text output relies on unit suffixes that scale with magnitude:

- Times: `us` (microseconds), `ms` (milliseconds), `s` (seconds),
  `m` (minutes — rarely seen).
- Byte counts: `B`, `KB`, `MB`, `GB` — decimal (×1000), not binary.
- Counts: `k` = ×1000 (for Req/Sec), `M` = ×1,000,000.

The parser must detect the suffix per-field and convert. A regex
like `([0-9.]+)(us|ms|s|m|KB|MB|GB|B|k|M)?` per token handles most
cases; care is needed because `m` alone (minutes) collides with `ms`
as a substring — anchor with a trailing word boundary.

### Ground-truth assertions

Unlike the canonical sample benchmark's tests 1–3, wrk's measurements
are **not** fixed quantities. p99 latency for this particular endpoint
will depend on the runner's CPU, concurrent noise, and TCP stack
timing. Parser tests for wrk must therefore use **loose** assertions
— presence-of-key and plausible-range rather than tight numeric
bounds:

- Assert `results[0]["attributes"]["test_name"] == "homepage"`.
- Assert `results[0]["timestamp"] == 0`.
- Assert the set of metric names includes `latency_avg`, `p50`,
  `p99`, `requests_per_sec`, `transfer_per_sec` (intersection, not
  exact equality — wrk's output is stable but a parser might legit-
  imately choose to emit more or fewer fields).
- Assert each latency metric has `value > 0` and a time unit.
- Assert `requests_per_sec > 0`.

This is weaker than the `2.0 < mean < 2.3` check we get from tests
1–3 in other frameworks — but it still verifies the parser is
actually reading the right fields, not just producing structurally
valid garbage.

### Failure mode

wrk exits non-zero if it cannot connect to the target at all
(connection refused, DNS failure). In that case there is no
meaningful report — stderr will carry something like
`unable to connect to localhost:8080 Connection refused` and
`output.txt` will contain that instead of a report. The parser
should detect the absence of a `Requests/sec:` line, emit a result
with `passed: false`, and either empty `metrics` or a single
informational entry. A wrk run that completes but reports
`Non-2xx or 3xx responses:` on any line should also mark
`passed: false`.

### Relationship to the fork

The predecessor TypeScript project at
[`nyrkio/change-detection`](https://github.com/nyrkio/change-detection)
did **not** have a wrk parser. This is a clean-slate implementation
— no fixtures to crib, no prior art to align with.

## Considered but not adopted

### wrk2

[wrk2](https://github.com/giltene/wrk2) is Gil Tene's fork that adds
(a) a `-R<rate>` constant-throughput mode that corrects for
coordinated omission, and (b) HDR histogram output with extended
percentiles (p99.9, p99.99, …). Its text report is a superset of
wrk's: everything a wrk parser handles, wrk2 also emits in the same
format, plus extra percentile lines.

We deliberately ship only the wrk variant for now:

- The Ubuntu `apt` repo has `wrk` but not `wrk2`; adopting wrk2 would
  mean building it from source in CI, which is a meaningful
  maintenance cost for a marginal parser improvement.
- The wrk2 output format is a superset, so a wrk parser can consume
  wrk2 output with minor extensions (additional percentile rows)
  when the need arises.
- The synthetic-benchmark question is the same either way: wrk and
  wrk2 both measure real HTTP load, neither maps onto the canonical
  sleep-based ground truth.

If downstream demand for wrk2-specific features (extended
percentiles, constant throughput mode) shows up, we can add a
`frameworks/loadtest/wrk2/` framework that builds wrk2 from source
and captures its extended output.
